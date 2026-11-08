"""Things given away: gone from the inventory, kept on record, and recoverable."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import apply_changes


def create(client, name, **fields):
    response = client.post("/api/items", data={"payload": json.dumps({"name": name, **fields})})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def gift(client, item_id, to="Kathy Brown"):
    return client.post(f"/api/items/{item_id}/gift", json={"to": to})


def names(client, **params):
    return [i["name"] for i in client.get("/api/items", params=params).json()["items"]]


quiet = {"log": lambda _: None}


def test_a_gift_leaves_the_inventory_but_is_kept_with_its_recipient(signed_in):
    kindle = create(signed_in, "Kindle", purchase_price_minor=227900, currency="SEK")
    create(signed_in, "Lamp")

    response = gift(signed_in, kindle)

    assert response.status_code == 200
    assert names(signed_in) == ["Lamp"]
    assert signed_in.get("/api/items").json()["total"] == 1
    assert names(signed_in, gifted="true") == ["Kindle"]
    detail = signed_in.get(f"/api/items/{kindle}").json()
    assert detail["gifted_to"] == "Kathy Brown"
    assert detail["gifted_at"]
    assert detail["purchase_price_minor"] == 227900


def test_a_recipient_is_optional(signed_in):
    toy = create(signed_in, "Soft toy")

    assert gift(signed_in, toy, to=None).status_code == 200

    detail = signed_in.get(f"/api/items/{toy}").json()
    assert detail["gifted_to"] is None
    assert detail["gifted_at"]
    assert names(signed_in) == []


def test_bringing_a_gift_back_restores_it(signed_in):
    kindle = create(signed_in, "Kindle")
    gift(signed_in, kindle)

    response = signed_in.delete(f"/api/items/{kindle}/gift")

    assert response.status_code == 200
    assert names(signed_in) == ["Kindle"]
    assert names(signed_in, gifted="true") == []
    assert signed_in.get(f"/api/items/{kindle}").json()["gifted_to"] is None


def test_gifting_something_that_does_not_exist_is_a_404(signed_in):
    assert gift(signed_in, "nope").status_code == 404


def test_gifts_leave_the_stats_and_the_room_counts(signed_in, rooms):
    kept = {"purchase_price_minor": 1000, "currency": "SEK", "room_id": rooms["Closet"]}
    create(signed_in, "Mine", **kept)
    given = create(signed_in, "Theirs", **(kept | {"purchase_price_minor": 9000}))
    gift(signed_in, given)

    stats = signed_in.get("/api/stats").json()
    closet = next(r for r in signed_in.get("/api/rooms").json() if r["name"] == "Closet")

    assert stats["entries"] == 1
    assert stats["totals"] == {"SEK": 1000}
    assert closet["item_count"] == 1


def test_a_gift_is_not_offered_as_a_possible_duplicate(signed_in):
    given = create(signed_in, "Fiskars knife")
    gift(signed_in, given)

    found = signed_in.get("/api/items/similar", params={"name": "Fiskars knife"}).json()

    assert found == []


def test_a_new_item_can_be_recorded_as_a_gift_and_is_not_added_twice(signed_in):
    new = {
        "shop": "ORMS",
        "order": "15129",
        "line": 1,
        "name": "Pentax 17",
        "second_hand": False,
        "category": "Electronics",
        "gift_to": "Kathy Brown",
    }
    changes = {"new_items": [new]}

    apply_changes.run(signed_in, changes, **quiet)
    apply_changes.run(signed_in, changes, **quiet)

    assert names(signed_in) == []
    assert names(signed_in, gifted="true") == ["Pentax 17"]


def test_an_existing_item_can_be_marked_as_a_gift_by_a_script_more_than_once(signed_in):
    create(signed_in, "Soft toy", descriptor_notes="IKEA order 1, line 11.")
    changes = {"updates": [{"ref": "IKEA order 1, line 11.", "gift": True}]}

    apply_changes.run(signed_in, changes, **quiet)
    apply_changes.run(signed_in, changes, **quiet)

    assert names(signed_in) == []
    assert names(signed_in, gifted="true") == ["Soft toy"]
