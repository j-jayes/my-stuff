"""Fetch a product page the owner pasted and pull out its image and title."""

import ipaddress
import socket
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
JSON_LD_MAX_CHARS = 4_000
TEXT_MAX_CHARS = 4_000


class BlockedUrl(Exception):
    """The URL is not something we are willing to fetch."""


@dataclass
class PageMetadata:
    title: str | None
    image_url: str | None
    # The page reduced to something worth putting in a prompt. See page_digest.
    digest: str = ""


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


def extract_metadata(html: str, page_url: str) -> PageMetadata:
    soup = BeautifulSoup(html, "html.parser")

    def meta(**attrs) -> str | None:
        tag = soup.find("meta", attrs=attrs)
        return tag.get("content") if tag else None

    title = meta(property="og:title") or meta(name="twitter:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    image = meta(property="og:image") or meta(name="twitter:image")

    return PageMetadata(title=title or None, image_url=_safe_image_url(image, page_url))


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


async def fetch_page_metadata(url: str, timeout: float) -> PageMetadata:
    validate_url(url)
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text[:MAX_HTML_BYTES]
    page = extract_metadata(html, str(response.url))
    page.digest = page_digest(html, str(response.url))
    return page


async def download_image(url: str, timeout: float, max_bytes: int) -> tuple[bytes, str]:
    """Fetch an image the scraper found, so the item owns its own copy."""
    validate_url(url)
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if not content_type.startswith("image/"):
            raise BlockedUrl(f"That URL returned {content_type or 'no content type'}, not an image")
        if len(response.content) > max_bytes:
            raise BlockedUrl("That image is too large")
        return response.content, content_type
