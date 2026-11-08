"""Rooms, moves and corrections applied to items already in the inventory."""

import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from tests.conftest import PASSWORD

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import apply_changes
import import_items


def create(client, name, **fields):
    response = client.post("/api/items", data={"payload": json.dumps({"name": name, **fields})})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def item(client, item_id):
    return client.get(f"/api/items/{item_id}").json()


def room_names(client):
    return [r["name"] for r in client.get("/api/rooms").json()]


quiet = {"log": lambda _: None}


def import_items_png():
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "PNG")
    return buffer.getvalue()


def test_makes_rooms_and_moves_every_matching_item(signed_in):
    books = [create(signed_in, f"Title {n} (book)") for n in range(3)]
    other = create(signed_in, "Lamp")
    changes = {
        "rooms": ["Bookshelf"],
        "updates": [{"name_contains": "(book)", "many": True, "room": "Bookshelf"}],
    }

    apply_changes.run(signed_in, changes, **quiet)

    assert "Bookshelf" in room_names(signed_in)
    assert {item(signed_in, b)["room"]["name"] for b in books} == {"Bookshelf"}
    assert item(signed_in, other)["room"] is None


def test_running_twice_does_not_fail_on_the_room_that_now_exists(signed_in):
    create(signed_in, "A (book)")
    changes = {
        "rooms": ["Bookshelf"],
        "updates": [{"name_contains": "(book)", "many": True, "room": "Bookshelf"}],
    }

    apply_changes.run(signed_in, changes, **quiet)
    apply_changes.run(signed_in, changes, **quiet)

    assert room_names(signed_in).count("Bookshelf") == 1


def test_corrects_quantity_and_leaves_the_rest_of_the_item_alone(signed_in):
    bulb = create(
        signed_in,
        "KAJPLATS bulb",
        quantity=2,
        purchase_price_minor=9900,
        currency="SEK",
        descriptor_notes="IKEA order 20260503, line 10.",
    )
    changes = {"updates": [{"ref": "IKEA order 20260503, line 10.", "quantity": 1}]}

    apply_changes.run(signed_in, changes, **quiet)

    updated = item(signed_in, bulb)
    assert updated["quantity"] == 1
    assert updated["name"] == "KAJPLATS bulb"
    assert updated["purchase_price_minor"] == 9900


def test_corrects_a_price_without_touching_the_date(signed_in):
    knife = create(
        signed_in,
        "All Steel brödkniv",
        purchase_price_minor=60000,
        currency="SEK",
        purchase_date="2025-06-01",
    )
    changes = {"updates": [{"name": "All Steel brödkniv", "price": 499, "currency": "SEK"}]}

    apply_changes.run(signed_in, changes, **quiet)

    updated = item(signed_in, knife)
    assert updated["purchase_price_minor"] == 49900
    assert updated["currency"] == "SEK"
    assert updated["purchase_date"] == "2025-06-01"


def test_a_match_that_is_not_unique_stops_before_anything_changes(signed_in):
    first = create(signed_in, "Lamp one")
    create(signed_in, "Lamp two")
    changes = {
        "rooms": ["Elsewhere"],
        "updates": [{"name_contains": "Lamp", "room": "Elsewhere"}],
    }

    with pytest.raises(SystemExit, match="Lamp"):
        apply_changes.run(signed_in, changes, **quiet)

    assert "Elsewhere" not in room_names(signed_in)
    assert item(signed_in, first)["room"] is None


def test_a_match_that_finds_nothing_stops(signed_in):
    with pytest.raises(SystemExit, match="Missing"):
        apply_changes.run(signed_in, {"updates": [{"name": "Missing", "quantity": 1}]}, **quiet)


def test_new_items_can_go_straight_into_a_new_room_without_an_order(signed_in):
    new = {
        "ref": "Home Assistant hardware: server.",
        "notes": "Runs Home Assistant.",
        "brand": "Lenovo",
        "name": "ThinkPad 13 2nd Gen",
        "second_hand": False,
        "category": "Electronics",
        "room": "Piece of Wood",
    }
    changes = {"rooms": ["Piece of Wood"], "new_items": [new]}

    apply_changes.run(signed_in, changes, **quiet)
    apply_changes.run(signed_in, changes, **quiet)

    listed = signed_in.get("/api/items", params={"q": "ThinkPad"}).json()["items"]
    assert len(listed) == 1
    created = item(signed_in, listed[0]["id"])
    assert created["room"]["name"] == "Piece of Wood"
    assert created["descriptor_notes"] == "Runs Home Assistant. Home Assistant hardware: server."
    assert created["purchase_date"] is None


def test_import_module_still_formats_order_references():
    line = {"shop": "IKEA", "order": "1", "line": 2}
    assert import_items._reference(line) == "IKEA order 1, line 2."


def category_names(client):
    return [c["name"] for c in client.get("/api/categories").json()]


def test_makes_a_category_and_moves_items_into_it(signed_in, categories):
    machine = create(signed_in, "Sewing machine", category_id=categories["Small Appliances"])
    changes = {
        "categories": ["Sewing Equipment"],
        "updates": [{"name": "Sewing machine", "category": "Sewing Equipment"}],
    }

    apply_changes.run(signed_in, changes, **quiet)
    apply_changes.run(signed_in, changes, **quiet)

    assert category_names(signed_in).count("Sewing Equipment") == 1
    assert item(signed_in, machine)["category"]["name"] == "Sewing Equipment"


def test_a_move_to_an_unknown_category_stops_before_anything_changes(signed_in):
    lamp = create(signed_in, "Lamp")
    changes = {"updates": [{"name": "Lamp", "quantity": 2}, {"name": "Lamp", "category": "Nope"}]}

    with pytest.raises(SystemExit, match="Nope"):
        apply_changes.run(signed_in, changes, **quiet)

    assert item(signed_in, lamp)["quantity"] == 1


def test_a_category_can_be_made_inside_another(signed_in):
    bike = create(signed_in, "Bike")
    changes = {
        "categories": ["Cycling", {"name": "Bikes", "parent": "Cycling"}],
        "updates": [{"name": "Bike", "category": "Bikes"}],
    }

    apply_changes.run(signed_in, changes, **quiet)
    apply_changes.run(signed_in, changes, **quiet)

    rows = {c["name"]: c for c in signed_in.get("/api/categories").json()}
    assert rows["Bikes"]["parent_id"] == rows["Cycling"]["id"]
    assert item(signed_in, bike)["category"]["name"] == "Bikes"


def test_an_item_can_be_picked_by_id_and_given_a_product_page(signed_in):
    first, second = create(signed_in, "Socks"), create(signed_in, "Socks")
    changes = {"updates": [{"id": second, "source_url": "https://example.com/socks"}]}

    apply_changes.run(signed_in, changes, **quiet)

    assert item(signed_in, second)["source_url"] == "https://example.com/socks"
    assert item(signed_in, first)["source_url"] is None


def test_a_photo_is_fetched_for_an_existing_item(signed_in, monkeypatch):
    fetched = []

    async def fake(url, timeout, max_bytes):
        fetched.append(url)
        return import_items_png(), "image/png"

    monkeypatch.setattr("app.routers.items.download_image", fake)
    lamp = create(signed_in, "Lamp")

    apply_changes.run(
        signed_in, {"updates": [{"id": lamp, "image_url": "https://example.com/a.png"}]}, **quiet
    )

    assert fetched == ["https://example.com/a.png"]
    assert item(signed_in, lamp)["image_url"]


def test_a_photo_that_cannot_be_fetched_is_reported_and_the_rest_still_happen(client, monkeypatch):
    async def refused(url, timeout, max_bytes):
        raise RuntimeError("403")

    monkeypatch.setattr("app.routers.items.download_image", refused)
    # A real deployment answers 500 here; the default test client would re-raise instead.
    lenient = TestClient(app, raise_server_exceptions=False)
    import_items.login(lenient, PASSWORD)
    lamp, chair = create(lenient, "Lamp"), create(lenient, "Chair")
    logged = []

    apply_changes.run(
        lenient,
        {
            "updates": [
                {"id": lamp, "image_url": "https://example.com/a.png", "quantity": 2},
                {"id": chair, "quantity": 3},
            ]
        },
        log=logged.append,
    )

    assert item(lenient, lamp)["quantity"] == 2
    assert item(lenient, chair)["quantity"] == 3
    assert any(line.startswith("no photo") and "Lamp" in line for line in logged)
