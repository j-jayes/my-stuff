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
    # Twelve top-level categories, plus the nineteen shelves under three of them.
    assert len(categories) == 31


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


def test_two_items_do_not_share_image_keys(signed_in, photo):
    """The id must exist before the image key is built, or every photo overwrites the last."""
    first = create(signed_in, name="First", photo=photo)
    second = create(signed_in, name="Second", photo=photo)

    assert "None" not in first["image_url"]
    assert first["image_url"] != second["image_url"]
    assert first["thumb_url"] != second["thumb_url"]


def test_a_bad_replacement_image_leaves_the_existing_photo_intact(signed_in, photo):
    item = create(signed_in, photo=photo)

    rejected = signed_in.patch(
        f"/api/items/{item['id']}",
        data={"payload": json.dumps({})},
        files={"image": ("broken.png", b"not an image at all", "image/png")},
    )

    assert rejected.status_code == 400
    assert signed_in.get(item["thumb_url"]).status_code == 200


def test_an_item_is_one_of_a_thing_unless_told_otherwise(signed_in):
    """Every row that existed before quantity did is a single object, so 1 is the default."""
    item = create(signed_in)

    assert item["quantity"] == 1


def test_a_set_of_things_is_one_item_with_a_count(signed_in):
    """Six drinking glasses are one line in the inventory, not six (FR-009)."""
    item = create(
        signed_in, name="Drinking glass", quantity=6, purchase_price_minor=4500, currency="SEK"
    )

    assert item["quantity"] == 6
    # The price is per glass; the total is the caller's arithmetic, not a stored field.
    assert item["purchase_price_minor"] == 4500

    listed = signed_in.get("/api/items").json()["items"]
    assert [i["quantity"] for i in listed if i["id"] == item["id"]] == [6]


def test_a_quantity_below_one_is_refused(signed_in):
    response = signed_in.post(
        "/api/items", data={"payload": json.dumps({"name": "Nothing", "quantity": 0})}
    )

    assert response.status_code == 400


def test_a_quantity_can_be_corrected_afterwards(signed_in):
    item = create(signed_in, quantity=4)

    updated = signed_in.patch(
        f"/api/items/{item['id']}", data={"payload": json.dumps({"quantity": 2})}
    )

    assert updated.status_code == 200
    assert updated.json()["quantity"] == 2
    # A partial patch must not disturb anything it did not name.
    assert updated.json()["name"] == "Ercol chair"


def test_a_patch_that_says_nothing_about_quantity_leaves_it_alone(signed_in):
    """quantity carries a default, so a partial patch must not silently reset a set of six
    back to one."""
    item = create(signed_in, quantity=6)

    updated = signed_in.patch(
        f"/api/items/{item['id']}", data={"payload": json.dumps({"brand": "Duralex"})}
    )

    assert updated.json()["quantity"] == 6


def test_a_thing_is_bought_new_unless_told_otherwise(signed_in):
    item = create(signed_in)

    assert item["second_hand"] is False


def test_a_thing_can_be_recorded_as_bought_second_hand(signed_in):
    """Half a wardrobe is bought used, and what was paid for it says nothing about that."""
    item = create(signed_in, name="Oxford shirt, blue", second_hand=True)

    assert item["second_hand"] is True
    assert signed_in.get(f"/api/items/{item['id']}").json()["second_hand"] is True


def test_a_patch_that_says_nothing_about_second_hand_leaves_it_alone(signed_in):
    """It carries a default, so a partial patch must not quietly turn a used shirt new."""
    item = create(signed_in, second_hand=True)

    updated = signed_in.patch(
        f"/api/items/{item['id']}", data={"payload": json.dumps({"brand": "Asket"})}
    )

    assert updated.json()["second_hand"] is True


def test_second_hand_can_be_corrected_afterwards(signed_in):
    item = create(signed_in, second_hand=True)

    updated = signed_in.patch(
        f"/api/items/{item['id']}", data={"payload": json.dumps({"second_hand": False})}
    )

    assert updated.status_code == 200
    assert updated.json()["second_hand"] is False


def test_the_brands_already_in_use_can_be_listed(signed_in):
    create(signed_in, name="Chair", brand="Ercol")
    create(signed_in, name="Stool", brand="Ercol")
    create(signed_in, name="Lamp", brand="IKEA")
    create(signed_in, name="Rug")

    brands = signed_in.get("/api/items/brands").json()

    # Commonest first, so the field suggests what is actually being typed.
    assert brands == [{"name": "Ercol", "item_count": 2}, {"name": "IKEA", "item_count": 1}]


def test_a_brand_that_only_differs_in_case_reuses_the_spelling_already_there(signed_in):
    """The database holds both "IKEA" and "Ikea" as separate brands. One of them is a typo
    and there is no way to tell which, so whichever arrived first wins from now on."""
    create(signed_in, name="Shelf", brand="IKEA")

    item = create(signed_in, name="Chair", brand="  ikea ")

    assert item["brand"] == "IKEA"
    assert signed_in.get("/api/items/brands").json() == [{"name": "IKEA", "item_count": 2}]


def test_the_spelling_most_items_already_use_is_the_one_that_wins(signed_in, settings):
    """Mixed spellings can only be legacy data — normalisation converges everything written
    after it — and the live database has exactly this: "Ikea" twice and "IKEA" once. Picking
    whichever row the database returned first would make the answer depend on scan order, so
    the rows are written straight in here to reproduce the state that actually exists.
    """
    import sqlite3

    for name in ("Shelf", "Chair", "Table"):
        create(signed_in, name=name, brand="IKEA")
    legacy = sqlite3.connect(settings.db_path)
    legacy.execute("UPDATE items SET brand = 'Ikea' WHERE name IN ('Chair', 'Table')")
    legacy.commit()
    legacy.close()

    item = create(signed_in, name="Lamp", brand="ikea")

    assert item["brand"] == "Ikea"


def test_a_genuinely_new_brand_is_kept_as_typed(signed_in):
    item = create(signed_in, name="Pan", brand="Skeppshult")

    assert item["brand"] == "Skeppshult"


def test_renaming_a_brand_on_one_item_does_not_touch_the_others(signed_in):
    """Normalisation is about how a brand is stored, not a shared record to be edited."""
    first = create(signed_in, name="Shelf", brand="IKEA")
    create(signed_in, name="Chair", brand="IKEA")

    signed_in.patch(f"/api/items/{first['id']}", data={"payload": json.dumps({"brand": "Habitat"})})

    assert {b["name"] for b in signed_in.get("/api/items/brands").json()} == {"IKEA", "Habitat"}


def test_an_image_url_can_be_attached_to_an_item_that_already_exists(signed_in, monkeypatch):
    """source_image_url is part of ItemWrite and was honoured when creating an item but
    silently ignored when patching one, so a request to attach a found photograph returned
    200 and did nothing at all."""

    async def fake_download(url, timeout, max_bytes):
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (400, 300), (10, 90, 160)).save(buffer, "PNG")
        return buffer.getvalue(), "image/png"

    monkeypatch.setattr("app.routers.items.download_image", fake_download)
    item = create(signed_in)
    assert item["thumb_url"] is None

    updated = signed_in.patch(
        f"/api/items/{item['id']}",
        data={"payload": json.dumps({"source_image_url": "https://cdn.example.com/chair.jpg"})},
    )

    assert updated.status_code == 200
    assert updated.json()["thumb_url"] and updated.json()["image_url"]
    assert signed_in.get(updated.json()["thumb_url"]).status_code == 200
