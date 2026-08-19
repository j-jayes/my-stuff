"""The scraper fetches a URL the owner pasted. That makes it a request-forgery surface: it must
never be usable to reach the metadata server or anything else inside the network.
"""

import pytest

from app.scrape import BlockedUrl, extract_metadata, validate_url


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
