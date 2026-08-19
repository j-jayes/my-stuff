import json


def create(client, photo=None, **fields):
    payload = {"name": "Ercol chair", **fields}
    files = {"image": ("photo.png", photo, "image/png")} if photo else None
    response = client.post("/api/items", data={"payload": json.dumps(payload)}, files=files)
    assert response.status_code == 201, response.text
    return response.json()


def test_the_default_rooms_and_categories_are_seeded(rooms, categories):
    assert set(rooms) == {"Kitchen", "Bedroom", "Lounge", "Bathroom", "Storage Room"}
    assert "Clothing & Accessories" in categories
    assert len(categories) == 9


def test_an_item_saves_with_its_photo_and_gets_a_thumbnail(signed_in, photo, rooms, categories):
    item = create(
        signed_in,
        photo=photo,
        room_id=rooms["Lounge"],
        category_id=categories["Furniture"],
        brand="Ercol",
        purchase_price_minor=450000,
        currency="SEK",
        purchase_date="2024-03-11",
    )

    assert item["room"]["name"] == "Lounge"
    assert item["thumb_url"] and item["image_url"]
    assert item["purchase_price_minor"] == 450000

    thumb = signed_in.get(item["thumb_url"])
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/webp"
    # The whole point of a thumbnail: browsing must not pull the original down.
    original = signed_in.get(item["image_url"])
    assert len(thumb.content) < len(original.content)


def test_an_item_can_be_saved_with_no_photo_and_no_optional_fields(signed_in):
    """Extraction failing, or the owner skipping the camera, must not block a save (FR-004)."""
    item = create(signed_in)

    assert item["name"] == "Ercol chair"
    assert item["image_url"] is None
    assert item["room"] is None


def test_an_item_needs_a_name(signed_in):
    response = signed_in.post("/api/items", data={"payload": json.dumps({"name": "   "})})

    assert response.status_code == 400


def test_a_price_without_a_currency_is_refused(signed_in):
    response = signed_in.post(
        "/api/items", data={"payload": json.dumps({"name": "Thing", "purchase_price_minor": 100})}
    )

    assert response.status_code == 400


def test_a_purchase_date_in_the_future_is_refused(signed_in):
    response = signed_in.post(
        "/api/items", data={"payload": json.dumps({"name": "Thing", "purchase_date": "2999-01-01"})}
    )

    assert response.status_code == 400


def test_items_filter_by_room_and_by_category_independently(signed_in, rooms, categories):
    create(signed_in, name="Kettle", room_id=rooms["Kitchen"], category_id=categories["Tools"])
    create(signed_in, name="Sofa", room_id=rooms["Lounge"], category_id=categories["Furniture"])

    in_kitchen = signed_in.get("/api/items", params={"room_id": rooms["Kitchen"]}).json()
    tools_anywhere = signed_in.get("/api/items", params={"category_id": categories["Tools"]}).json()

    assert [i["name"] for i in in_kitchen["items"]] == ["Kettle"]
    assert [i["name"] for i in tools_anywhere["items"]] == ["Kettle"]


def test_search_matches_name_brand_and_notes(signed_in):
    create(signed_in, name="Blue kettle")
    create(signed_in, name="Toaster", brand="Dualit")
    create(signed_in, name="Lamp", descriptor_notes="A brass reading lamp")

    assert signed_in.get("/api/items", params={"q": "kettle"}).json()["total"] == 1
    assert signed_in.get("/api/items", params={"q": "dualit"}).json()["total"] == 1
    assert signed_in.get("/api/items", params={"q": "brass"}).json()["total"] == 1
    assert signed_in.get("/api/items", params={"q": "nothing here"}).json()["total"] == 0


def test_search_and_filters_combine(signed_in, rooms):
    create(signed_in, name="Kettle", room_id=rooms["Kitchen"])
    create(signed_in, name="Kettle bell", room_id=rooms["Lounge"])

    result = signed_in.get("/api/items", params={"q": "kettle", "room_id": rooms["Kitchen"]}).json()

    assert result["total"] == 1


def test_editing_changes_only_the_fields_that_were_sent(signed_in, rooms):
    item = create(signed_in, brand="Ercol", room_id=rooms["Lounge"])

    updated = signed_in.patch(
        f"/api/items/{item['id']}", data={"payload": json.dumps({"name": "Windsor chair"})}
    ).json()

    assert updated["name"] == "Windsor chair"
    assert updated["brand"] == "Ercol"
    assert updated["room"]["name"] == "Lounge"


def test_replacing_a_photo_regenerates_the_thumbnail_and_drops_the_old_files(signed_in, photo):
    item = create(signed_in, photo=photo)
    old_image_url = item["image_url"]

    updated = signed_in.patch(
        f"/api/items/{item['id']}",
        data={"payload": json.dumps({})},
        files={"image": ("new.png", photo, "image/png")},
    ).json()

    assert signed_in.get(updated["thumb_url"]).status_code == 200
    if updated["image_url"] != old_image_url:
        assert signed_in.get(old_image_url).status_code == 404


def test_deleting_an_item_removes_it_and_its_images(signed_in, photo):
    item = create(signed_in, photo=photo)

    assert signed_in.delete(f"/api/items/{item['id']}").status_code == 204

    assert signed_in.get(f"/api/items/{item['id']}").status_code == 404
    assert signed_in.get(item["thumb_url"]).status_code == 404
    assert signed_in.get("/api/items").json()["total"] == 0


def test_an_unknown_room_is_refused_rather_than_silently_ignored(signed_in):
    response = signed_in.post(
        "/api/items", data={"payload": json.dumps({"name": "Thing", "room_id": "made-up"})}
    )

    assert response.status_code == 400


def test_a_room_still_holding_items_cannot_be_deleted(signed_in, rooms):
    create(signed_in, room_id=rooms["Kitchen"])

    response = signed_in.delete(f"/api/rooms/{rooms['Kitchen']}")

    assert response.status_code == 409
    assert "1 item is still" in response.json()["detail"]


def test_an_empty_room_can_be_deleted_and_new_ones_added(signed_in, rooms):
    assert signed_in.delete(f"/api/rooms/{rooms['Bathroom']}").status_code == 204

    created = signed_in.post("/api/rooms", json={"name": "Garage"})
    assert created.status_code == 201

    duplicate = signed_in.post("/api/rooms", json={"name": "garage"})
    assert duplicate.status_code == 409


def test_suggested_fields_survive_a_reload_so_the_ui_can_still_mark_them(signed_in):
    item = create(signed_in, ai_suggested_fields=["name", "brand"])

    reloaded = signed_in.get(f"/api/items/{item['id']}").json()

    assert reloaded["ai_suggested_fields"] == ["name", "brand"]
