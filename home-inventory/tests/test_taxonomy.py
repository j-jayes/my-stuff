"""Categories are two levels deep: Kitchenware has children, everything else is flat.

Rooms stay a single level, which is why they share the router factory but not these tests.
"""

import json

KITCHEN_SUBCATEGORIES = {
    "Cookware",
    "Bakeware",
    "Kitchen Knives",
    "Cutting Boards",
    "Kitchen Tools & Utensils",
    "Dinnerware",
    "Serveware & Trays",
    "Drinkware & Glassware",
    "Cutlery",
    "Barware",
    "Food Storage",
    "Kitchen Textiles",
}


def entries(client) -> dict[str, dict]:
    return {c["name"]: c for c in client.get("/api/categories").json()}


def test_kitchenware_is_seeded_with_its_shelves(signed_in):
    """ "Kitchenware" covered a cooking spoon, a bread knife and a casserole alike."""
    by_name = entries(signed_in)
    kitchenware = by_name["Kitchenware"]

    assert kitchenware["parent_id"] is None
    assert {name for name, c in by_name.items() if c["parent_id"] == kitchenware["id"]} == (
        KITCHEN_SUBCATEGORIES
    )


def test_only_the_categories_that_need_shelves_have_them(signed_in):
    by_name = entries(signed_in)
    with_shelves = {
        "Kitchenware",
        "Bedding & Linen",
        "Bathroom & Grooming",
        "Clothing & Accessories",
    }

    for name in ("Furniture", "Lighting", "Electronics", "Tools", "Decor", "Miscellaneous"):
        assert by_name[name]["parent_id"] is None, name

    parents = {c["parent_id"] for c in by_name.values() if c["parent_id"]}
    assert parents == {by_name[name]["id"] for name in with_shelves}


def test_clothing_is_shelved_by_what_an_outfit_is_made_of(signed_in):
    """Not by garment type. Picking an outfit means choosing a top, then a bottom, then shoes;
    a shirt and a t-shirt answer the same question and belong on the same shelf."""
    by_name = entries(signed_in)
    clothing = by_name["Clothing & Accessories"]

    assert {name for name, c in by_name.items() if c["parent_id"] == clothing["id"]} == {
        "Tops",
        "Bottoms",
        "Shoes",
        "Outerwear",
        "Accessories",
    }


def test_towels_have_exactly_one_home(signed_in):
    """Splitting bath towels from beach towels would mean deciding, item by item, which a
    given towel is. Bedding & Linen owns all of them."""
    by_name = entries(signed_in)

    assert by_name["Towels"]["parent_id"] == by_name["Bedding & Linen"]["id"]
    assert "Bath Linen" not in by_name


def test_a_subcategory_can_be_added_under_a_parent(signed_in):
    parent = entries(signed_in)["Furniture"]

    response = signed_in.post(
        "/api/categories", json={"name": "Seating", "parent_id": parent["id"]}
    )

    assert response.status_code == 201
    assert response.json()["parent_id"] == parent["id"]


def test_the_taxonomy_is_only_two_levels_deep(signed_in):
    """A shelf inside a shelf inside a shelf is a filing system, not an inventory."""
    child = entries(signed_in)["Cookware"]

    response = signed_in.post(
        "/api/categories", json={"name": "Saucepans", "parent_id": child["id"]}
    )

    assert response.status_code == 400


def test_a_subcategory_of_something_that_does_not_exist_is_refused(signed_in):
    response = signed_in.post("/api/categories", json={"name": "Ghost", "parent_id": "no-such-id"})

    assert response.status_code == 400


def test_a_parent_with_children_cannot_be_deleted(signed_in):
    """Deleting Kitchenware would orphan twelve shelves and the items on them."""
    kitchenware = entries(signed_in)["Kitchenware"]

    response = signed_in.delete(f"/api/categories/{kitchenware['id']}")

    assert response.status_code == 409


def test_filtering_by_a_parent_includes_everything_on_its_shelves(signed_in):
    """Picking "Kitchenware" must not show an empty list just because every item is filed
    one level down."""
    by_name = entries(signed_in)
    for name, category in (("Chef's knife", "Kitchen Knives"), ("Casserole", "Cookware")):
        signed_in.post(
            "/api/items",
            data={"payload": json.dumps({"name": name, "category_id": by_name[category]["id"]})},
        )
    signed_in.post(
        "/api/items",
        data={"payload": json.dumps({"name": "Sofa", "category_id": by_name["Furniture"]["id"]})},
    )

    page = signed_in.get(f"/api/items?category_id={by_name['Kitchenware']['id']}").json()

    assert sorted(i["name"] for i in page["items"]) == ["Casserole", "Chef's knife"]
    assert page["total"] == 2


def test_a_parents_count_includes_its_children(signed_in):
    by_name = entries(signed_in)
    signed_in.post(
        "/api/items",
        data={"payload": json.dumps({"name": "Wok", "category_id": by_name["Cookware"]["id"]})},
    )

    refreshed = entries(signed_in)

    assert refreshed["Cookware"]["item_count"] == 1
    assert refreshed["Kitchenware"]["item_count"] == 1
