"""Fetch a product page the owner pasted and pull out its image and title."""

import ipaddress
import json
import re
import socket
import unicodedata
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# Retail sites routinely serve a stub to unknown clients. Identifying ourselves honestly gets
# usable HTML from most of them without pretending to be a browser.
USER_AGENT = "my-stuff-inventory/0.1 (personal home inventory; +https://github.com/)"
MAX_HTML_BYTES = 2 * 1024 * 1024
# Enough for the meta tags, the schema.org block and the opening body text of a product page —
# the three real product pages this was built against digest to 6-8k. Past that a page is
# navigation and reviews, which cost tokens and tell the model nothing.
DIGEST_MAX_CHARS = 12_000
# Enough for the http->https and country-redirect hops a retail site does; short enough that a
# loop gives up quickly.
MAX_REDIRECTS = 5
JSON_LD_MAX_CHARS = 4_000
TEXT_MAX_CHARS = 4_000


# Plain colour words only, and deliberately no shades. "Amber" is the yellow Duralex and
# "plum" is the purple one, so counting those as colours would have this rejecting the very
# pages it is meant to find, while gaining nothing: a page that names no colour it recognises
# is simply left to the word check below.
COLOURS = frozenset(
    {
        "white",
        "black",
        "grey",
        "gray",
        "red",
        "blue",
        "green",
        "yellow",
        "beige",
        "brown",
        "pink",
        "purple",
        "orange",
        "turquoise",
        "silver",
        "gold",
        "oak",
        "birch",
        "pine",
        "walnut",
    }
)


# Shades a shop uses instead of a plain colour. They are not colours for the purpose of
# disagreeing — amber is the yellow Duralex, plum the purple one — but they do show that a
# page is about one particular variant rather than the plain version.
SHADES = frozenset(
    {
        "amber",
        "plum",
        "sapphire",
        "marine",
        "navy",
        "ivory",
        "cream",
        "charcoal",
        "teal",
        "olive",
        "mustard",
        "rose",
        "burgundy",
        "taupe",
        "lilac",
        "lila",
        "graphite",
        "sand",
        "clear",
        "smoke",
    }
)


def names_a_variant(text: str) -> bool:
    """Does this text say which version of the thing it is about?

    The Duralex Le Picardie page is a genuine product page for the plain glass and names no
    colour at all, so nothing contradicts a note asking for the purple one and its photograph
    would have been used. If a colour was asked for, a page that names no variant whatsoever
    is not the page.
    """
    return bool(_colour_words(text) or _shade_words(text))


def _shade_words(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c)).casefold()
    return set(re.findall(r"[a-z0-9]+", folded)) & SHADES


def colour_conflict(wanted: str, offered: str) -> bool:
    """Does one text name a variant the other rules out?

    Only a colour that was actually asked for can be contradicted, and only by a colour that
    is actually named: a page that mentions no colour is not evidence of anything either way.
    Amber is not yellow and plum is not purple as words, so this deliberately does not demand
    a match — it only refuses a flat disagreement.
    """
    asked = _colour_words(wanted)
    got = _colour_words(offered)
    return bool(asked and got and not (asked & got))


def _colour_words(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c)).casefold()
    return set(re.findall(r"[a-z0-9]+", folded)) & COLOURS


class BlockedUrl(Exception):
    """The URL is not something we are willing to fetch."""


@dataclass
class PageMetadata:
    title: str | None
    image_url: str | None
    # The page reduced to something worth putting in a prompt. See page_digest.
    digest: str = ""
    # Where the fetch actually ended up. Search results arrive as redirects through
    # vertexaisearch.cloud.google.com, so the address asked for is not the address read.
    url: str = ""
    # Whether the page says it is about one product. See _declares_a_product.
    is_product: bool = False


def _check_scheme_and_literal_address(url: str) -> str:
    """The half of validation that needs no network: scheme, and any literal IP in the host.

    Kept separate so parsing HTML stays a pure function — a parser that does DNS lookups is
    both slow and impossible to test offline.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BlockedUrl(f"Only http and https URLs can be fetched, not {parsed.scheme!r}")
    if not parsed.hostname:
        raise BlockedUrl("URL has no host")

    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return parsed.hostname  # a name, not an address; resolved at fetch time
    if not literal.is_global or literal.is_multicast:
        raise BlockedUrl(f"{literal} is not a public address")
    return parsed.hostname


def validate_url(url: str) -> None:
    """Refuse anything that is not a public http(s) address, resolving names to be sure.

    The owner pastes these, so this is not untrusted input in the usual sense — but the app
    runs next to a metadata server that hands out credentials to anything that asks, and a
    mistyped or hostile URL must not be able to reach it. Call this immediately before
    fetching, never earlier.
    """
    hostname = _check_scheme_and_literal_address(url)

    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise BlockedUrl(f"Could not resolve {hostname}") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_multicast:
            raise BlockedUrl(f"{hostname} resolves to the non-public address {address}")


def _safe_image_url(candidate: str | None, page_url: str) -> str | None:
    if not candidate:
        return None
    absolute = urljoin(page_url, candidate.strip())
    try:
        _check_scheme_and_literal_address(absolute)
    except BlockedUrl:
        return None
    return absolute


def _structured_image(soup: BeautifulSoup) -> str | None:
    """The product photograph out of a schema.org block.

    Worth the trouble because some pages — IKEA's among them — serve
    `<meta property="og:image" content="">` while the JSON-LD still carries the real image.
    `image` may be a bare URL, a list, or ImageObjects; take the first thing that looks usable.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            blocks = json.loads(script.string)
        except ValueError:
            continue  # a page with broken JSON is not worth failing the whole scrape over
        for block in blocks if isinstance(blocks, list) else [blocks]:
            if not isinstance(block, dict):
                continue
            candidates = block.get("image")
            for candidate in candidates if isinstance(candidates, list) else [candidates]:
                if isinstance(candidate, str) and candidate.strip():
                    return candidate
                if isinstance(candidate, dict) and candidate.get("contentUrl"):
                    return candidate["contentUrl"]
    return None


def _declares_a_product(soup: BeautifulSoup) -> bool:
    """Does the page claim to be about a single product?

    A search for a Duralex tumbler happily returns cervera.se/varumarken/duralex, which lists
    everything the brand makes: it shares the brand with the item, which is all the word check
    needs, and its picture is a shop banner. Both of the ways a page declares itself a product
    are standard and already parsed here, so this costs nothing extra.
    """
    og_type = soup.find("meta", attrs={"property": "og:type"})
    if og_type and "product" in (og_type.get("content") or "").casefold():
        return True

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            blocks = json.loads(script.string)
        except ValueError:
            continue
        for block in blocks if isinstance(blocks, list) else [blocks]:
            if isinstance(block, dict) and "product" in str(block.get("@type", "")).casefold():
                return True
    return False


def extract_metadata(html: str, page_url: str) -> PageMetadata:
    soup = BeautifulSoup(html, "html.parser")

    def meta(**attrs) -> str | None:
        tag = soup.find("meta", attrs=attrs)
        return tag.get("content") if tag else None

    title = meta(property="og:title") or meta(name="twitter:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    image = meta(property="og:image") or meta(name="twitter:image") or _structured_image(soup)

    return PageMetadata(
        title=title or None,
        image_url=_safe_image_url(image, page_url),
        is_product=_declares_a_product(soup),
    )


def page_digest(html: str, page_url: str) -> str:
    """Reduce a product page to the parts worth showing a language model.

    Three passes, cheapest signal first: the meta tags, then any schema.org JSON-LD (which is
    where retail sites state the exact price, currency and brand), then the visible text with
    the furniture stripped out. Raw HTML would be mostly markup and would blow the budget.

    What comes back is untrusted third-party text. It is labelled as data in the prompt, and
    the fields a page could try to steer — category, room — are constrained to enums built
    from the owner's own lists, so the worst case is a bad suggestion in an editable form.
    """
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []

    for tag in soup.find_all("meta"):
        key = tag.get("property") or tag.get("name")
        content = tag.get("content")
        if (
            key
            and content
            and (key.startswith(("og:", "twitter:", "product:")) or key == "description")
        ):
            parts.append(f"{key}: {content}")

    for script in soup.find_all("script", type="application/ld+json"):
        if script.string:
            parts.append("JSON-LD: " + " ".join(script.string.split())[:JSON_LD_MAX_CHARS])

    # Decompose before get_text, or every script body and stylesheet lands in the middle of
    # the page's actual words.
    for tag in soup(["script", "style", "nav", "footer", "header", "svg", "noscript"]):
        tag.decompose()
    parts.append("TEXT: " + " ".join(soup.get_text(" ").split())[:TEXT_MAX_CHARS])

    return "\n".join(parts)[:DIGEST_MAX_CHARS]


async def _get_following_redirects(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """Fetch, checking every hop rather than only the first.

    httpx's own follow_redirects would resolve the chain without asking us again, so a page
    could bounce the fetch onto the metadata server after the guard had already passed. Each
    location is validated before it is requested, so an internal address is never reached at
    all — not merely discarded afterwards.
    """
    for _ in range(MAX_REDIRECTS + 1):
        validate_url(url)
        response = await client.get(url)
        if not response.is_redirect:
            return response
        location = response.headers.get("location")
        if not location:
            return response
        url = str(response.url.join(location))
    raise BlockedUrl(f"That address redirected more than {MAX_REDIRECTS} times")


async def fetch_page_metadata(url: str, timeout: float, transport=None) -> PageMetadata:
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
        transport=transport,
    ) as client:
        response = await _get_following_redirects(client, url)
        response.raise_for_status()
        html = response.text[:MAX_HTML_BYTES]
    page = extract_metadata(html, str(response.url))
    page.digest = page_digest(html, str(response.url))
    page.url = str(response.url)
    return page


async def download_image(url: str, timeout: float, max_bytes: int) -> tuple[bytes, str]:
    """Fetch an image the scraper found, so the item owns its own copy."""
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, headers={"User-Agent": USER_AGENT}
    ) as client:
        response = await _get_following_redirects(client, url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if not content_type.startswith("image/"):
            raise BlockedUrl(f"That URL returned {content_type or 'no content type'}, not an image")
        if len(response.content) > max_bytes:
            raise BlockedUrl("That image is too large")
        return response.content, content_type
