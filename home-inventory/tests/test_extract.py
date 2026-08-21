"""What is sent to the model, and what is made of what comes back.

Nothing here reaches Vertex except the test marked `integration`, which the default run
excludes. The rest use a stub client, because the interesting logic is the assembly of the
request and the conversion of the answer — not the model.
"""

import pytest

from app.config import Settings
from app.extract import (
    ItemSuggestion,
    _to_minor,
    find_product_pages,
    resolve_name,
    suggest_item,
)


def _grounded(*uris):
    """A response shaped like a grounded one: sources in the metadata, not in the prose."""
    web = [type("Web", (), {"uri": uri, "title": uri, "domain": uri})() for uri in uris]
    chunks = [type("Chunk", (), {"web": w})() for w in web]
    metadata = type("Meta", (), {"grounding_chunks": chunks})()
    return [type("Candidate", (), {"grounding_metadata": metadata})()]


class StubModels:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.candidates = _grounded()
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"text": self.payload, "candidates": self.candidates})()


class StubClient:
    def __init__(self, payload: str) -> None:
        self.models = StubModels(payload)


ANSWER = """
{"name": "All Steel brodkniv", "brand": "Fiskars", "category": "Kitchenware",
 "subcategory": "Kitchen Knives", "room": "Kitchen", "descriptor_notes": "A bread knife.",
 "price": "599", "currency": "SEK", "purchase_date": "2025-06-01", "quantity": 1}
"""

LISTS = {
    "categories": ["Kitchenware", "Furniture"],
    "subcategories": ["Kitchen Knives", "Cookware"],
    "rooms": ["Kitchen", "Lounge"],
}


@pytest.fixture
def stub(monkeypatch):
    client = StubClient(ANSWER)
    monkeypatch.setattr("app.extract._client", lambda *a, **k: client)
    return client


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("1995", 199500),
        ("1995.00", 199500),
        ("1 995", 199500),  # a plain space thousands separator
        ("1 995", 199500),  # and the non-breaking one Swedish sites actually print
        ("1995,50", 199550),
        ("1995.50", 199550),
        ("599", 59900),
        ("19.99", 1999),
        ("0", 0),
        (None, None),
        ("", None),
        ("ask in store", None),
    ],
)
def test_a_printed_price_becomes_minor_units(printed, expected):
    """The model reads the number off the page; multiplying by 100 is Python's job. A 100x
    error here would be silent, plausible, and land straight in the stored field."""
    assert _to_minor(printed) == expected


def test_the_owners_note_is_sent_verbatim(stub):
    suggest_item(Settings(), note="six of these, bought June 2025", **LISTS)

    sent = " ".join(str(part) for part in stub.models.calls[0]["contents"])
    assert "six of these, bought June 2025" in sent


def test_a_photo_a_page_and_a_note_can_all_be_sent_at_once(stub):
    suggest_item(
        Settings(),
        image=b"\x89PNG fake",
        content_type="image/png",
        page="og:title: All Steel",
        note="in the kitchen drawer",
        **LISTS,
    )

    contents = stub.models.calls[0]["contents"]
    assert len(contents) == 3
    rendered = " ".join(str(part) for part in contents)
    assert "og:title: All Steel" in rendered
    assert "in the kitchen drawer" in rendered


def test_nothing_at_all_is_refused_before_it_costs_anything(stub):
    """An empty request would bill for a hallucination."""
    with pytest.raises(ValueError):
        suggest_item(Settings(), **LISTS)

    assert stub.models.calls == []


def test_the_owners_own_lists_are_the_only_answers_allowed(stub):
    """Constraining the enums removes the "model invented a category" case at the source."""
    suggest_item(Settings(), note="a knife", **LISTS)

    schema = stub.models.calls[0]["config"].response_json_schema
    assert schema["properties"]["category"]["enum"] == ["Kitchenware", "Furniture"]
    assert schema["properties"]["subcategory"]["enum"] == ["Kitchen Knives", "Cookware", None]
    assert schema["properties"]["room"]["enum"] == ["Kitchen", "Lounge", None]


def test_the_answer_comes_back_as_an_item(stub):
    suggestion = suggest_item(Settings(), note="a knife", **LISTS)

    assert suggestion == ItemSuggestion(
        name="All Steel brodkniv",
        brand="Fiskars",
        category="Kitchenware",
        subcategory="Kitchen Knives",
        room="Kitchen",
        descriptor_notes="A bread knife.",
        price="599",
        currency="SEK",
        purchase_date="2025-06-01",
        quantity=1,
    )
    assert _to_minor(suggestion.price) == 59900


@pytest.mark.integration
def test_a_real_product_page_extracts_cleanly():
    """Hits Vertex for real. The failure this guards is the one the whole feature exists for:
    the row in the database reads "IVAR shelving unit, with 6 shelves/pine, 89x50x226 cm  -
    IKEA Sweden" because the old scraper took og:title verbatim.
    """
    import gzip
    from pathlib import Path

    from app.scrape import page_digest

    # Stored gzipped: the page is a megabyte of inlined script with the schema.org block at
    # the very end, and there is no honest way to trim it — cutting it loses the price.
    fixture = Path(__file__).parent / "fixtures" / "ikea-ivar.html.gz"
    html = gzip.decompress(fixture.read_bytes()).decode()
    digest = page_digest(html, "https://www.ikea.com/se/en/p/ivar-shelving-unit-pine-s09631216/")

    suggestion = suggest_item(
        Settings(),
        categories=["Furniture", "Kitchenware", "Electronics"],
        subcategories=["Cookware", "Kitchen Knives"],
        rooms=["Kitchen", "Lounge"],
        page=digest,
    )

    assert suggestion.brand == "IKEA"
    assert suggestion.category == "Furniture"
    assert "IVAR" in suggestion.name
    assert "IKEA Sweden" not in suggestion.name
    assert "89x50x226" not in suggestion.name
    # 1 995 kr on the page. Getting this wrong by 100x is the reason Python does the maths.
    assert _to_minor(suggestion.price) == 199500


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Lounge", "Lounge"),
        ("lounge", "Lounge"),  # the model echoes the note's casing, not the list's
        ("  KITCHEN  ", "Kitchen"),
        ("Symaskin", None),  # a real answer, and not a category anyone offered
        (None, None),
        ("", None),
    ],
)
def test_an_answer_is_matched_against_what_was_offered(answer, expected):
    assert resolve_name(["Kitchen", "Lounge"], answer) == expected


@pytest.mark.integration
@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("Duralex drinking tumbler in yellow", "yellow"),
        ("Duralex drinking tumbler in purple", "purple"),
        # "hermit" rather than "hermit crab": what matters is that this towel is tellable
        # apart from the fiddler crab one, and either wording achieves that. Demanding the
        # exact phrase made the test fail about a quarter of the time for no real reason.
        ("Mungo Folly beach towel in the hermit crab colourway", "hermit"),
    ],
)
def test_the_thing_that_tells_two_items_apart_stays_in_the_name(note, expected):
    """Six tumblers in three colours are three rows, and "drinking tumbler" three times over
    is useless in a grid. Whatever distinguishes one from the next belongs in the name, not
    only in the notes.
    """
    suggestion = suggest_item(
        Settings(),
        categories=["Kitchenware", "Furniture"],
        subcategories=["Drinkware & Glassware", "Kitchen Textiles"],
        rooms=["Kitchen", "Lounge"],
        note=note,
    )

    assert expected.casefold() in suggestion.name.casefold(), suggestion.name


def test_the_urls_come_from_the_search_results(stub):
    """Only ever from what search actually retrieved."""
    stub.models.candidates = _grounded(
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA",
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/BBB",
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA",
    )

    found = find_product_pages("Duralex Picardie tumbler amber", Settings())

    # Deduplicated; a repeated source is not worth a second fetch.
    assert found == [
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA",
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/BBB",
    ]
    # Search has to actually be switched on, or there is nothing to be grounded in.
    assert stub.models.calls[0]["config"].tools


def test_a_url_the_model_merely_wrote_down_is_never_used(stub):
    """The whole reason this changed. Asked for a URL the model writes a plausible one from
    memory — four Swedish retailer URLs in a row, every one a 404. A URL is only worth having
    if a search engine returned it."""
    stub.models.payload = "You want https://www.cervera.se/produkt/duralex-picardie-amber"
    stub.models.candidates = _grounded()

    assert find_product_pages("Duralex Picardie tumbler amber", Settings()) == []


def test_finding_nothing_is_not_an_error(stub):
    stub.models.candidates = _grounded()

    assert find_product_pages("a thing that does not exist", Settings()) == []


def test_the_search_going_wrong_is_not_an_error(stub, monkeypatch):
    """Not finding a photo is a normal outcome; it must not fail the whole suggestion."""

    def boom(*args, **kwargs):
        raise RuntimeError("Vertex is down")

    monkeypatch.setattr(stub.models, "generate_content", boom)

    assert find_product_pages("a thing", Settings()) == []


@pytest.mark.integration
def test_a_real_search_returns_real_sources():
    """Hits Vertex and the live web. The prompt has to be one the model answers in prose:
    asked for a bare URL it answers without citing anything and the sources come back empty,
    which is how this came to be reading invented URLs out of the prose in the first place.
    """
    # The model decides for itself whether a search is worth running, and now and then it
    # answers from memory and cites nothing. That is a real characteristic of this — the
    # caller gets an empty list and the item goes without a photograph — so the test asks a
    # few times rather than pretending one attempt is deterministic.
    attempts = [
        find_product_pages("Duralex Picardie tumbler 25cl in amber", Settings()) for _ in range(3)
    ]
    found = next((sources for sources in attempts if sources), [])

    assert found, "no attempt returned any sources at all"
    assert all(url.startswith("https://") for url in found)
    # Sources come back as redirects through Google, not as the shop's own address.
    assert any("vertexaisearch" in url for url in found)
