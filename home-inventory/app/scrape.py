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


class BlockedUrl(Exception):
    """The URL is not something we are willing to fetch."""


@dataclass
class PageMetadata:
    title: str | None
    image_url: str | None


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


async def fetch_page_metadata(url: str, timeout: float) -> PageMetadata:
    validate_url(url)
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text[:MAX_HTML_BYTES]
    return extract_metadata(html, str(response.url))


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
