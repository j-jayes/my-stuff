"""Rooms, moves and corrections applied to items already in the inventory."""

import json
import sys
from pathlib import Path

import pytest

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
