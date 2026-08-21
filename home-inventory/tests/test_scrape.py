"""The scraper fetches a URL the owner pasted. That makes it a request-forgery surface: it must
never be usable to reach the metadata server or anything else inside the network.
"""

import pytest

from app.scrape import (
    DIGEST_MAX_CHARS,
    MAX_REDIRECTS,
    BlockedUrl,
    extract_metadata,
    fetch_page_metadata,
    page_digest,
    validate_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/computeMetadata/v1/",  # GCP metadata server
        "http://localhost:8000/api/items",
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.4.4/",
        "http://0.0.0.0/",
        "file:///etc/passwd",
        "gopher://example.com/",
        "ftp://example.com/file",
    ],
)
def test_internal_and_non_http_urls_are_refused(url):
    with pytest.raises(BlockedUrl):
        validate_url(url)


@pytest.mark.parametrize(
    "url", ["https://example.com/product/1", "http://example.com/", "https://www.example.com/x"]
)
def test_ordinary_public_urls_are_allowed(url):
    validate_url(url)


def test_reads_opengraph_title_and_image():
    html = """
    <html><head>
      <meta property="og:title" content="Ercol Windsor Chair">
      <meta property="og:image" content="https://cdn.example.com/chair.jpg">
      <title>Ignore me</title>
    </head><body></body></html>
    """
    result = extract_metadata(html, "https://example.com/p/1")

    assert result.title == "Ercol Windsor Chair"
    assert result.image_url == "https://cdn.example.com/chair.jpg"


def test_falls_back_to_twitter_card_then_page_title():
    html = """
    <html><head>
      <meta name="twitter:image" content="/img/kettle.png">
      <title>Kettle | Example Shop</title>
    </head></html>
    """
    result = extract_metadata(html, "https://example.com/p/2")

    assert result.title == "Kettle | Example Shop"
    # Relative image URLs in the page must be resolved against the page, not returned as-is.
    assert result.image_url == "https://example.com/img/kettle.png"


def test_a_page_with_no_image_still_returns_a_title():
    """FR-006: no image found is a normal outcome, not an error."""
    result = extract_metadata("<html><head><title>Thing</title></head></html>", "https://e.com/")

    assert result.title == "Thing"
    assert result.image_url is None


def test_an_image_url_pointing_somewhere_internal_is_dropped():
    """A hostile page must not be able to make us fetch an internal address later."""
    html = '<html><head><meta property="og:image" content="http://169.254.169.254/x.jpg"></head></html>'

    result = extract_metadata(html, "https://example.com/")

    assert result.image_url is None


def test_the_digest_carries_the_structured_product_data():
    """The model gets JSON-LD if the page has it. That is where the exact price and brand
    live on every retail site checked (ikea.com, nordicnest.se, kitchenlab.se)."""
    html = """
    <html><head>
      <meta property="og:title" content="All Steel brodkniv">
      <meta name="description" content="A bread knife">
      <script type="application/ld+json">
        {"@type":"Product","name":"All Steel","brand":{"name":"Fiskars"},
         "offers":{"price":"599","priceCurrency":"SEK"}}
      </script>
      <style>.a { color: red }</style>
    </head><body><h1>All Steel brodkniv</h1><script>var tracking = 1;</script></body></html>
    """
    digest = page_digest(html, "https://example.com/p/1")

    assert "og:title: All Steel brodkniv" in digest
    assert "description: A bread knife" in digest
    assert '"priceCurrency":"SEK"' in digest
    assert "All Steel brodkniv" in digest.split("TEXT:")[1]
    # Script and style bodies are noise that would crowd out the page's actual words.
    assert "var tracking" not in digest
    assert "color: red" not in digest


def test_the_digest_is_capped():
    """A long page must not push the prompt into a size that costs more than the item."""
    html = "<html><body>" + ("word " * 100_000) + "</body></html>"

    assert len(page_digest(html, "https://example.com/")) <= DIGEST_MAX_CHARS


def test_a_page_with_nothing_useful_still_produces_a_digest():
    digest = page_digest("<html><body>Chair</body></html>", "https://example.com/")

    assert "Chair" in digest


def test_an_image_is_taken_from_structured_data_when_the_meta_tag_is_empty():
    """IKEA serves `<meta property="og:image" content="">` on some pages while the schema.org
    block still carries the real photograph."""
    html = """
    <html><head>
      <meta property="og:image" content="">
      <script type="application/ld+json">
        {"@type":"Product","name":"FORSÅ","image":[{"@type":"ImageObject",
         "contentUrl":"https://cdn.example.com/forsa.jpg"}]}
      </script>
    </head></html>
    """
    assert extract_metadata(html, "https://example.com/p/1").image_url == (
        "https://cdn.example.com/forsa.jpg"
    )


def test_a_plain_string_image_in_structured_data_is_understood():
    html = """
    <html><head><script type="application/ld+json">
      {"@type":"Product","image":"/img/pan.jpg"}
    </script></head></html>
    """
    assert extract_metadata(html, "https://example.com/p/1").image_url == (
        "https://example.com/img/pan.jpg"
    )


def test_the_meta_tag_still_wins_when_it_has_a_value():
    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.example.com/og.jpg">
      <script type="application/ld+json">{"@type":"Product","image":"https://cdn.example.com/ld.jpg"}</script>
    </head></html>
    """
    assert extract_metadata(html, "https://e.com/").image_url == "https://cdn.example.com/og.jpg"


def test_structured_data_that_is_not_json_is_ignored():
    html = '<html><head><script type="application/ld+json">{ oh dear </script></head></html>'

    assert extract_metadata(html, "https://e.com/").image_url is None


def _redirector(location: str):
    """A transport that answers every request with a redirect to a fixed location, so the
    redirect handling can be exercised without a network. Returns the transport and the list
    of URLs it was actually asked for."""
    import httpx

    requested: list[str] = []

    def handle(request):
        requested.append(str(request.url))
        return httpx.Response(302, headers={"location": location})

    return httpx.MockTransport(handle), requested


@pytest.mark.asyncio
async def test_a_redirect_towards_an_internal_address_is_refused():
    """The SSRF guard checked the URL it was given and then let httpx follow redirects
    unchecked, so a page could bounce the fetch onto the metadata server. That mattered little
    when the owner typed every URL; it matters a great deal now the model supplies them.
    """
    transport, requested = _redirector("http://169.254.169.254/computeMetadata/v1/")
    with pytest.raises(BlockedUrl):
        await fetch_page_metadata("https://example.com/p/1", 5.0, transport=transport)

    # The internal address must never have been requested at all.
    assert requested == ["https://example.com/p/1"]


@pytest.mark.asyncio
async def test_a_redirect_loop_gives_up():
    transport, requested = _redirector("https://example.com/p/1")
    with pytest.raises(BlockedUrl):
        await fetch_page_metadata("https://example.com/p/1", 5.0, transport=transport)

    assert len(requested) <= MAX_REDIRECTS + 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_live_ikea_catalogue_redirect_is_recognisable():
    """The failure that prompted the verification step: a product URL that does not exist is
    redirected to the catalogue and answered with 200, not 404. If IKEA ever starts returning
    a proper 404 this test fails and the check can be simplified.
    """
    page = await fetch_page_metadata(
        "https://www.ikea.com/se/sv/p/forsa-arbetslampa-vit-30146860/", 20.0
    )

    assert "sortiment" in (page.title or "").lower()
