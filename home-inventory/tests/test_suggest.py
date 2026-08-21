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


@pytest.fixture(autouse=True)
def no_searching(monkeypatch):
    """Nothing in this file may reach the network. Without this, every test that leaves a
    note unstubbed goes off and searches the real web and IKEA, which is slow and flaky."""

    async def no_ikea(*args, **kwargs):
        return None

    monkeypatch.setattr("app.routers.items.find_product_page", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.items.ikea_search", no_ikea)


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
    """The JSON-schema enum is guidance, not a guarantee — asked to file a sewing machine the
    model answered "Symaskin", which is in nobody's list. A name that does not exist must not
    throw away the top-level answer that does.
    """
    answer(monkeypatch, category="Small Appliances", subcategory="Symaskin")

    body = signed_in.post("/api/items/suggest", data={"note": "a sewing machine"}).json()

    assert body["category_id"] == categories["Small Appliances"]


def test_an_invented_category_leaves_the_field_empty(signed_in, monkeypatch):
    answer(monkeypatch, category="Gadgets", subcategory=None, room="Shed")

    body = signed_in.post("/api/items/suggest", data={"note": "a thing"}).json()

    assert body["category_id"] is None
    assert body["room_id"] is None
    assert "category" not in body["suggested_fields"]
    assert body["name"] == "All Steel brodkniv"


FOUND = PageMetadata(
    title="Duralex Picardie tumbler 25 cl",
    image_url="https://cdn.example.com/tertial.jpg",
    digest="og:title: Duralex Picardie tumbler",
)
# What IKEA actually serves for a product URL that does not exist: 200, and its catalogue.
WRONG_PAGE = PageMetadata(
    title="Se hela IKEA sortimentet & alla produkter online - IKEA",
    image_url="https://cdn.example.com/some-other-thing.jpg",
    digest="og:title: Se hela IKEA sortimentet",
)


def searching(monkeypatch, page, url="https://www.ikea.com/se/sv/p/tertial-vit-70355455/"):
    async def fake_fetch(target, timeout, **kwargs):
        return page

    monkeypatch.setattr("app.routers.items.find_product_page", lambda *a, **k: url)
    monkeypatch.setattr("app.routers.items.fetch_page_metadata", fake_fetch)


def test_a_typed_note_gets_a_photo_looked_up_for_it(signed_in, monkeypatch):
    """Nothing but words in: a product page is searched for, and its photo comes back. Not an
    IKEA item, which has its own path that never falls back to a web search."""
    answer(monkeypatch, name="Picardie tumbler")
    searching(monkeypatch, FOUND)

    body = signed_in.post("/api/items/suggest", data={"note": "Duralex Picardie tumbler"}).json()

    assert body["image_url"] == "https://cdn.example.com/tertial.jpg"
    assert body["source_url"] == "https://www.ikea.com/se/sv/p/tertial-vit-70355455/"


def test_an_ikea_item_never_falls_back_to_a_web_search(signed_in, monkeypatch):
    """IKEA's own catalogue is the authority on what IKEA sells. Asking a model instead is
    how a nickel-plated FORSÅ came back for a white one — right lamp, wrong finish, and a
    photograph that looks perfectly correct."""
    answer(monkeypatch, name="FORSÅ work lamp")
    asked_the_model = []
    monkeypatch.setattr(
        "app.routers.items.find_product_page", lambda *a, **k: asked_the_model.append(1)
    )

    body = signed_in.post("/api/items/suggest", data={"note": "IKEA FORSÅ work lamp white"}).json()

    assert asked_the_model == []
    assert body["image_url"] is None


def test_a_page_that_is_not_about_this_product_is_thrown_away(signed_in, monkeypatch):
    """A wrong IKEA product URL redirects to the catalogue and answers 200, so "it fetched"
    proves nothing. Without this check the catalogue's photograph would be attached to the
    lamp, which is worse than having no photograph at all.
    """
    answer(monkeypatch, name="TERTIAL work lamp")
    searching(monkeypatch, WRONG_PAGE)

    body = signed_in.post(
        "/api/items/suggest", data={"note": "IKEA TERTIAL work lamp white"}
    ).json()

    assert body["image_url"] is None
    assert body["source_url"] is None


def test_a_link_the_owner_pasted_is_never_second_guessed(signed_in, page, monkeypatch):
    """The check is for pages the model went and found. A URL typed by the owner is theirs to
    be wrong about."""
    answer(monkeypatch)

    body = signed_in.post("/api/items/suggest", data={"url": "https://example.com/p/1"}).json()

    assert body["image_url"] == "https://cdn.example.com/knife.jpg"


def test_no_search_happens_when_a_photo_was_supplied(signed_in, photo, monkeypatch):
    """The owner's own photograph of their own thing beats a stock product shot."""
    answer(monkeypatch)
    called = []
    monkeypatch.setattr("app.routers.items.find_product_page", lambda *a, **k: called.append(1))

    signed_in.post(
        "/api/items/suggest",
        data={"note": "a knife"},
        files={"image": ("photo.png", photo, "image/png")},
    )

    assert called == []


def test_an_ikea_item_is_looked_up_in_ikeas_own_search(signed_in, monkeypatch):
    """Their search knows the real article number. The model does not, and invents one."""
    from app.ikea import IkeaProduct

    answer(monkeypatch, name="TERTIAL work lamp")
    product = IkeaProduct(
        name="TERTIAL Work lamp",
        item_no="70355455",
        url="https://www.ikea.com/se/en/p/tertial-work-lamp-white-70355455/",
        image_url="https://www.ikea.com/img/tertial.jpg",
    )

    async def fake_search(*args, **kwargs):
        return product

    tertial = PageMetadata(
        title="TERTIAL Work lamp, white - IKEA",
        image_url="https://cdn.example.com/tertial.jpg",
        digest="og:title: TERTIAL Work lamp, white",
    )
    asked_the_model = []
    searching(monkeypatch, tertial, url=product.url)
    monkeypatch.setattr("app.routers.items.ikea_search", fake_search)
    monkeypatch.setattr(
        "app.routers.items.find_product_page", lambda *a, **k: asked_the_model.append(1)
    )

    body = signed_in.post(
        "/api/items/suggest", data={"note": "IKEA TERTIAL work lamp white"}
    ).json()

    assert body["source_url"] == product.url
    # No point asking a model to remember a URL when the retailer will simply tell us.
    assert asked_the_model == []


def test_an_ikea_result_in_the_wrong_colour_is_not_used(signed_in, monkeypatch):
    """Asked for a white FORSÅ their search returns the black one. Falling back to the model
    is fine; using the black lamp's photograph is not."""
    from app.ikea import IkeaProduct

    answer(monkeypatch, name="FORSÅ work lamp")

    async def fake_search(*args, **kwargs):
        return IkeaProduct(
            name="FORSÅ Work lamp",
            item_no="00146776",
            url="https://www.ikea.com/se/en/p/forsa-work-lamp-black-00146776/",
            image_url="https://www.ikea.com/img/forsa-black.jpg",
        )

    monkeypatch.setattr("app.routers.items.ikea_search", fake_search)
    monkeypatch.setattr("app.routers.items.find_product_page", lambda *a, **k: None)

    body = signed_in.post("/api/items/suggest", data={"note": "IKEA FORSÅ work lamp white"}).json()

    assert body["image_url"] is None
    assert body["source_url"] is None


def test_something_that_is_not_ikea_does_not_ask_ikea(signed_in, monkeypatch):
    answer(monkeypatch)
    asked = []

    async def fake_search(*args, **kwargs):
        asked.append(1)

    monkeypatch.setattr("app.routers.items.ikea_search", fake_search)
    monkeypatch.setattr("app.routers.items.find_product_page", lambda *a, **k: None)

    signed_in.post("/api/items/suggest", data={"note": "Duralex tumbler in yellow"})

    assert asked == []
