"""IKEA's own product search, used instead of asking a model to remember a URL.

Ten of the thirteen items that had no photograph were IKEA. The model produced URLs with the
right slug and an invented article number, which IKEA answers with a 302 to its catalogue and
a 200 — so the guess looked like a success. Their search returns the real article number.
"""

import httpx
import pytest

from app.ikea import IkeaProduct, matches, query_for, search

TERTIAL = {
    "results": [
        {
            "items": [
                {
                    "product": {
                        "name": "TERTIAL",
                        "typeName": "Work lamp",
                        "itemNo": "70355455",
                        "pipUrl": "https://www.ikea.com/se/en/p/tertial-work-lamp-white-70355455/",
                        "mainImageUrl": "https://www.ikea.com/img/tertial.jpg",
                    }
                }
            ]
        }
    ]
}


def _transport(payload, status=200):
    def handle(request):
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
async def test_a_product_is_found_with_its_real_article_number():
    product = await search("TERTIAL work lamp white", 10.0, transport=_transport(TERTIAL))

    assert product == IkeaProduct(
        name="TERTIAL Work lamp",
        item_no="70355455",
        url="https://www.ikea.com/se/en/p/tertial-work-lamp-white-70355455/",
        image_url="https://www.ikea.com/img/tertial.jpg",
    )


@pytest.mark.asyncio
async def test_nothing_found_is_not_an_error():
    assert await search("a thing", 10.0, transport=_transport({"results": []})) is None


@pytest.mark.asyncio
async def test_the_search_being_unavailable_is_not_an_error():
    """No photograph is a normal outcome. IKEA being down must not fail the suggestion."""
    assert await search("TERTIAL", 10.0, transport=_transport({}, status=503)) is None


def _product(name, slug):
    return IkeaProduct(
        name=name,
        item_no="1",
        url=f"https://www.ikea.com/se/en/p/{slug}/",
        image_url="https://i/x.jpg",
    )


@pytest.mark.parametrize(
    ("query", "name", "slug", "ok"),
    [
        ("TERTIAL work lamp white", "TERTIAL Work lamp", "tertial-work-lamp-white-70355455", True),
        # Answers the live search actually gave: the black lamp for a white one, and the
        # yellow chair for a red one. A photograph in the wrong colour looks right.
        ("FORSÅ work lamp white", "FORSÅ Work lamp", "forsa-work-lamp-black-00146776", False),
        ("VIHALS chair red", "VIHALS Chair", "vihals-chair-yellow-tibbleby-yellow-90621062", False),
        # And the dangerous one: an entirely different product that happens to share "white",
        # which no amount of colour checking would catch.
        ("FORSÅ work lamp white", "DVALA Fitted sheet", "dvala-fitted-sheet-white-00357226", False),
        # More than one colour in the slug is normal; sharing one is enough.
        (
            "KLEPPSTAD bed frame white",
            "KLEPPSTAD Bed frame",
            "kleppstad-bed-frame-white-vissle-beige-10492672",
            True,
        ),
        # No colour asked for, so there is nothing to contradict.
        (
            "ULLVIDE fitted sheet",
            "ULLVIDE Fitted sheet",
            "ullvide-fitted-sheet-white-20342724",
            True,
        ),
        (
            "HEKTAR work lamp grey",
            "HEKTAR Work lamp",
            "hektar-work-lamp-with-wireless-charging-70493764",
            True,
        ),
    ],
)
def test_only_the_product_that_was_asked_for_is_accepted(query, name, slug, ok):
    assert matches(query, _product(name, slug)) is ok


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        # The whole sentence finds nothing at all; the first eight words find the lamp.
        (
            "Ikea TERTIAL work lamp White metal work lamp fitted with a smart bulb.",
            "Ikea TERTIAL work lamp White metal work lamp",
        ),
        ("IKEA VIHALS chair in red", "IKEA VIHALS chair in red"),
        ("KLEPPSTAD bed frame. A bed frame in white.", "KLEPPSTAD bed frame"),
    ],
)
def test_a_note_is_trimmed_to_something_a_search_box_can_use(note, expected):
    assert query_for(note) == expected


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_live_search_returns_the_article_number_off_the_receipt():
    """Hits IKEA. The article number is the point: 203.427.24 is what the receipt says, and
    20342724 is what their URL ends with. A model guessing that number is what produced a
    catalogue page dressed up as a 200."""
    product = await search("ULLVIDE fitted sheet 160x200 white", 20.0)

    assert product is not None
    assert product.item_no == "20342724"
    assert product.image_url and product.image_url.startswith("https://")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_article_number_finds_its_product_exactly():
    """Dotted, as printed on the receipt."""
    product = await search("504.814.69", 20.0)

    assert product is not None and product.item_no == "50481469"
    assert "abygda" in product.url


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_live_search_still_answers_the_wrong_colour_for_forsa():
    """The reason matches() exists. If IKEA ever starts returning the white one, this fails
    and the check can be reconsidered."""
    product = await search("FORSÅ work lamp white", 20.0)

    assert product is not None
    assert not matches("FORSÅ work lamp white", product)


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("Ikea KLEPPSTAD bed frame 104.926.72 A bed frame in white", "104.926.72"),
        ("IKEA ULLVIDE fitted sheet, article 20342724", "20342724"),
        ("IKEA TERTIAL work lamp in white", "IKEA TERTIAL work lamp in white"),
    ],
)
def test_an_article_number_is_the_whole_query(note, expected):
    """Searching by words returns a KLEPPSTAD in the wrong size; the number off the receipt
    returns the one that was bought."""
    assert query_for(note) == expected


@pytest.mark.parametrize(
    ("query", "item_no", "ok"),
    [
        ("104.926.72", "10492672", True),
        ("10492672", "10492672", True),
        ("104.926.72", "00492677", False),
    ],
)
def test_a_numbered_search_is_checked_against_the_number(query, item_no, ok):
    product = IkeaProduct(
        name="KLEPPSTAD Bed frame",
        item_no=item_no,
        url="https://x/p/kleppstad-1/",
        image_url="https://i",
    )

    assert matches(query, product) is ok
