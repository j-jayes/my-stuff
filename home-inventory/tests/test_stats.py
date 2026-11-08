"""The money page: what has been spent, where, and on what."""

import json


def create(client, name, **fields):
    response = client.post("/api/items", data={"payload": json.dumps({"name": name, **fields})})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def priced(minor, currency="SEK", **fields):
    return {"purchase_price_minor": minor, "currency": currency, **fields}


def listed(stats, name):
    return next(i for i in stats["items"] if i["name"] == name)


def test_totals_multiply_by_quantity_and_keep_currencies_apart(signed_in):
    create(signed_in, "Glasses", quantity=4, **priced(1000))
    create(signed_in, "Bike", **priced(100000, "USD"))
    create(signed_in, "Mystery")

    stats = signed_in.get("/api/stats").json()

    assert stats["entries"] == 3
    assert stats["units"] == 6
    assert stats["unpriced"] == 1
    assert stats["totals"] == {"SEK": 4000, "USD": 100000}


def test_second_hand_spending_is_reported_so_the_replacement_figure_can_be_qualified(signed_in):
    create(signed_in, "Shirt", second_hand=True, **priced(10000))
    create(signed_in, "Found laptop", second_hand=True, **priced(0))
    create(signed_in, "Lamp", **priced(5000))

    stats = signed_in.get("/api/stats").json()

    assert stats["second_hand_entries"] == 2
    assert stats["second_hand_totals"] == {"SEK": 10000}


def test_the_shop_comes_from_the_order_reference_in_the_notes(signed_in):
    create(signed_in, "Shirt", descriptor_notes="Size L. Sellpy order Abc123, line 2.", **priced(1))
    create(
        signed_in, "Tee", descriptor_notes="Size S. DEDICATED. order 565838, line 1.", **priced(1)
    )
    create(
        signed_in,
        "Vacuum",
        descriptor_notes="Includes charger. Dyson order 1791290143, line 1.",
        **priced(259000),
    )

    stats = signed_in.get("/api/stats").json()

    assert listed(stats, "Shirt")["shop"] == "Sellpy"
    assert listed(stats, "Tee")["shop"] == "DEDICATED."
    assert listed(stats, "Vacuum")["shop"] == "Dyson"


def test_new_ikea_things_count_as_ikea_and_unknowns_are_said_to_be_unknown(signed_in):
    create(signed_in, "Lamp", brand="Ikea", **priced(5000))
    create(signed_in, "Old chair", brand="Ikea", second_hand=True, **priced(9000))
    create(signed_in, "Spoon", brand="Gestura", descriptor_notes="Lovely.", **priced(1000))

    stats = signed_in.get("/api/stats").json()

    assert listed(stats, "Lamp")["shop"] == "IKEA"
    assert listed(stats, "Old chair")["shop"] == "Not recorded"
    assert listed(stats, "Spoon")["shop"] == "Not recorded"


def test_each_item_says_where_it_is_and_what_it_cost_in_all(signed_in, categories, rooms):
    create(
        signed_in,
        "Shirts",
        brand="Levi's",
        quantity=3,
        category_id=categories["Tops"],
        room_id=rooms["Closet"],
        purchase_date="2021-03-01",
        second_hand=True,
        **priced(1000),
    )
    create(signed_in, "Mystery")

    stats = signed_in.get("/api/stats").json()
    shirts, mystery = listed(stats, "Shirts"), listed(stats, "Mystery")

    assert shirts["category"] == "Clothing & Accessories"
    assert shirts["room"] == "Closet"
    assert shirts["brand"] == "Levi's"
    assert shirts["minor"] == 3000
    assert shirts["currency"] == "SEK"
    assert shirts["quantity"] == 3
    assert shirts["date"] == "2021-03-01"
    assert shirts["second_hand"] is True
    assert "thumb_url" in shirts
    assert (mystery["category"], mystery["room"], mystery["minor"]) == (None, None, None)


def test_gifts_stay_out_of_the_items_and_are_added_up_by_person(signed_in):
    keep = create(signed_in, "Mine", **priced(1000))
    for name, to in [("Book", "Ann"), ("Pen", "Ann"), ("Hat", None)]:
        given = create(signed_in, name, **priced(2000))
        assert signed_in.post(f"/api/items/{given}/gift", json={"to": to}).status_code == 200

    stats = signed_in.get("/api/stats").json()

    assert [i["id"] for i in stats["items"]] == [keep]
    assert stats["gifts"][0] == {"label": "Ann", "entries": 2, "spent": {"SEK": 4000}}
    assert stats["gifts"][1] == {"label": "Not named", "entries": 1, "spent": {"SEK": 2000}}


def test_the_page_needs_a_session(client):
    assert client.get("/api/stats").status_code == 401
