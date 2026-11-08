"""The money page: what has been spent, where, and on what."""

import json


def create(client, name, **fields):
    response = client.post("/api/items", data={"payload": json.dumps({"name": name, **fields})})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def priced(minor, currency="SEK", **fields):
    return {"purchase_price_minor": minor, "currency": currency, **fields}


def row(rows, label):
    return next(r for r in rows if r["label"] == label)


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
    note = "Size L. Sellpy order Abc123, line 2."
    create(signed_in, "Shirt", descriptor_notes=note, **priced(10000))
    create(signed_in, "Jeans", descriptor_notes="Sellpy order Abc123, line 3.", **priced(20000))
    create(
        signed_in,
        "Tee",
        descriptor_notes="Size S. DEDICATED. order 565838, line 1.",
        **priced(34900),
    )
    create(
        signed_in,
        "Vacuum",
        descriptor_notes="Includes charger. Dyson order 1791290143, line 1.",
        **priced(259000),
    )

    shops = signed_in.get("/api/stats").json()["by_shop"]

    assert row(shops, "Sellpy") == {"label": "Sellpy", "entries": 2, "spent": {"SEK": 30000}}
    assert row(shops, "DEDICATED.")["spent"] == {"SEK": 34900}
    assert shops[0]["label"] == "Dyson"


def test_new_ikea_things_count_as_ikea_and_unknowns_are_said_to_be_unknown(signed_in):
    create(signed_in, "Lamp", brand="Ikea", **priced(5000))
    create(signed_in, "Old chair", brand="Ikea", second_hand=True, **priced(9000))
    create(signed_in, "Spoon", brand="Gestura", descriptor_notes="Lovely.", **priced(1000))

    shops = signed_in.get("/api/stats").json()["by_shop"]

    assert row(shops, "IKEA")["spent"] == {"SEK": 5000}
    assert row(shops, "Not recorded")["spent"] == {"SEK": 10000}


def test_shelves_roll_up_to_their_category_and_rooms_are_counted(signed_in, categories, rooms):
    create(signed_in, "Shirt", category_id=categories["Tops"], **priced(1000))
    create(signed_in, "Shoes", category_id=categories["Shoes"], **priced(2000))
    create(signed_in, "Thing", room_id=rooms["Closet"], **priced(500))

    stats = signed_in.get("/api/stats").json()

    assert row(stats["by_category"], "Clothing & Accessories")["spent"] == {"SEK": 3000}
    assert row(stats["by_category"], "No category")["spent"] == {"SEK": 500}
    assert row(stats["by_room"], "Closet")["spent"] == {"SEK": 500}
    assert row(stats["by_room"], "No room")["entries"] == 2


def test_years_run_newest_first_with_undated_last(signed_in):
    create(signed_in, "Old", purchase_date="2021-03-01", **priced(1000))
    create(signed_in, "New", purchase_date="2025-03-01", **priced(1000))
    create(signed_in, "Undated", **priced(9000))

    years = signed_in.get("/api/stats").json()["by_year"]

    assert [y["label"] for y in years] == ["2025", "2021", "Undated"]


def test_most_expensive_ranks_the_whole_line_in_kronor_only(signed_in):
    create(signed_in, "Glasses", quantity=10, **priced(1000))
    create(signed_in, "Chair", **priced(5000))
    create(signed_in, "Bike", **priced(99999900, "USD"))

    top = signed_in.get("/api/stats").json()["most_expensive"]

    assert [(t["name"], t["minor"]) for t in top] == [("Glasses", 10000), ("Chair", 5000)]


def test_the_page_needs_a_session(client):
    assert client.get("/api/stats").status_code == 401
