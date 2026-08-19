"""The one endpoint behind all three ways of adding something.

The model itself is stubbed: what matters here is that names come back as ids the form can
use, that a nonsense date is dropped rather than raising, and that a page we already fetched
is still worth something when the model is unreachable.
"""

import pytest

from app.extract import ExtractionUnavailable, ItemSuggestion
from app.scrape import PageMetadata

PAGE = PageMetadata(
    title="All Steel brodkniv | Nordic Nest",
    image_url="https://cdn.example.com/knife.jpg",
    digest="og:title: All Steel brodkniv",
)


@pytest.fixture
def page(monkeypatch):
    async def fake_fetch(url, timeout):
        return PAGE

    monkeypatch.setattr("app.routers.items.fetch_page_metadata", fake_fetch)


def answer(monkeypatch, **overrides):
    suggestion = ItemSuggestion(
        **{
            "name": "All Steel brodkniv",
            "brand": "Fiskars",
            "category": "Kitchenware",
            "subcategory": "Kitchen Knives",
            "room": "Kitchen",
            "descriptor_notes": "A bread knife.",
            "price": "599",
            "currency": "SEK",
            "purchase_date": "2025-06-01",
            "quantity": 1,
            **overrides,
        }
    )
    monkeypatch.setattr("app.routers.items.suggest_item", lambda *a, **k: suggestion)


def unavailable(monkeypatch):
    def boom(*args, **kwargs):
        raise ExtractionUnavailable("Vertex is down")

    monkeypatch.setattr("app.routers.items.suggest_item", boom)


def test_nothing_to_go_on_is_refused(signed_in):
    assert signed_in.post("/api/items/suggest", data={}).status_code == 400


def test_a_link_comes_back_as_a_filled_in_form(signed_in, categories, rooms, page, monkeypatch):
    answer(monkeypatch)

    body = signed_in.post("/api/items/suggest", data={"url": "https://example.com/p/1"}).json()

    assert body["name"] == "All Steel brodkniv"
    assert body["brand"] == "Fiskars"
    # The shelf, not the parent: the model picked a subcategory and it wins.
    assert body["category_id"] == categories["Kitchen Knives"]
    assert body["room_id"] == rooms["Kitchen"]
    assert body["purchase_price_minor"] == 59900
    assert body["currency"] == "SEK"
    assert body["source_url"] == "https://example.com/p/1"
    assert body["image_url"] == "https://cdn.example.com/knife.jpg"
    assert set(body["suggested_fields"]) >= {"name", "brand", "category", "room", "price"}


def test_the_top_level_category_is_used_when_no_shelf_fits(signed_in, categories, monkeypatch):
    answer(monkeypatch, category="Furniture", subcategory=None)

    body = signed_in.post("/api/items/suggest", data={"note": "a sofa"}).json()

    assert body["category_id"] == categories["Furniture"]


def test_a_typed_note_alone_is_enough(signed_in, monkeypatch):
    """No photo, no link — just what the owner knows."""
    answer(monkeypatch)

    response = signed_in.post("/api/items/suggest", data={"note": "bread knife in the kitchen"})

    assert response.status_code == 200
    assert response.json()["name"] == "All Steel brodkniv"


def test_a_date_in_the_future_is_dropped_rather_than_raising(signed_in, monkeypatch):
    """ItemWrite refuses a future purchase date. A suggestion is not a write, so an odd
    answer must blank the field instead of failing the whole request."""
    answer(monkeypatch, purchase_date="2099-01-01")

    body = signed_in.post("/api/items/suggest", data={"note": "a knife"}).json()

    assert body["purchase_date"] is None
    assert body["name"] == "All Steel brodkniv"


def test_an_unreadable_date_is_dropped(signed_in, monkeypatch):
    answer(monkeypatch, purchase_date="sometime last summer")

    assert signed_in.post("/api/items/suggest", data={"note": "x"}).json()["purchase_date"] is None


def test_a_page_is_still_worth_something_when_the_model_is_down(signed_in, page, monkeypatch):
    """The link path must never be worse than it was before the model was on it."""
    unavailable(monkeypatch)

    response = signed_in.post("/api/items/suggest", data={"url": "https://example.com/p/1"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "All Steel brodkniv | Nordic Nest"
    assert body["image_url"] == "https://cdn.example.com/knife.jpg"
    assert body["suggested_fields"] == ["name"]


def test_a_note_with_no_page_has_nothing_to_fall_back_to(signed_in, monkeypatch):
    unavailable(monkeypatch)

    assert signed_in.post("/api/items/suggest", data={"note": "a knife"}).status_code == 502


def test_a_name_that_differs_only_in_case_still_resolves(signed_in, rooms, monkeypatch):
    """Asked about "in lounge", the model answers "lounge". Matching exactly would drop it."""
    answer(monkeypatch, room="lounge", category="kitchenware", subcategory="kitchen knives")

    body = signed_in.post("/api/items/suggest", data={"note": "a knife in the lounge"}).json()

    assert body["room_id"] == rooms["Lounge"]


def test_an_invented_subcategory_falls_back_to_the_category(signed_in, categories, monkeypatch):
    """The JSON-schema enum is guidance, not a guarantee — asked for a lamp with only kitchen
    shelves on offer, the model returned "Lighting", which is in nobody's list. A name that
    does not exist must not throw away the top-level answer that does.
    """
    answer(monkeypatch, category="Furniture", subcategory="Lighting")

    body = signed_in.post("/api/items/suggest", data={"note": "a lamp"}).json()

    assert body["category_id"] == categories["Furniture"]


def test_an_invented_category_leaves_the_field_empty(signed_in, monkeypatch):
    answer(monkeypatch, category="Gadgets", subcategory=None, room="Shed")

    body = signed_in.post("/api/items/suggest", data={"note": "a thing"}).json()

    assert body["category_id"] is None
    assert body["room_id"] is None
    assert "category" not in body["suggested_fields"]
    assert body["name"] == "All Steel brodkniv"
