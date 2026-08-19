"""A board that does not reopen exactly as it was left is worse than no board at all (FR-018)."""

import json


def make_item(client, name):
    response = client.post("/api/items", data={"payload": json.dumps({"name": name})})
    assert response.status_code == 201
    return response.json()["id"]


def test_a_board_reopens_with_every_placement_exactly_as_it_was_left(signed_in):
    board = signed_in.post("/api/boards", json={"name": "Lounge redesign"}).json()
    items = [make_item(signed_in, f"Item {i}") for i in range(4)]
    placements = [
        {
            "item_id": item_id,
            "position_x": 100.5 * i,
            "position_y": 40.25 * i,
            "scale": 1.0 + i / 10,
            "z_index": 3 - i,
        }
        for i, item_id in enumerate(items)
    ]

    signed_in.put(f"/api/boards/{board['id']}/placements", json={"placements": placements})
    reopened = signed_in.get(f"/api/boards/{board['id']}").json()

    by_item = {p["item"]["id"]: p for p in reopened["placements"]}
    assert len(by_item) == 4
    for original in placements:
        saved = by_item[original["item_id"]]
        assert saved["position_x"] == original["position_x"]
        assert saved["position_y"] == original["position_y"]
        assert saved["scale"] == original["scale"]
        assert saved["z_index"] == original["z_index"]


def test_saving_a_board_replaces_its_placements_rather_than_adding_to_them(signed_in):
    board = signed_in.post("/api/boards", json={"name": "Outfit"}).json()
    first, second = make_item(signed_in, "Coat"), make_item(signed_in, "Boots")
    place = lambda item_id: {"item_id": item_id, "position_x": 1, "position_y": 2}  # noqa: E731

    signed_in.put(f"/api/boards/{board['id']}/placements", json={"placements": [place(first)]})
    result = signed_in.put(
        f"/api/boards/{board['id']}/placements", json={"placements": [place(second)]}
    ).json()

    assert [p["item"]["id"] for p in result["placements"]] == [second]


def test_removing_an_item_from_a_board_leaves_the_item_alone(signed_in):
    board = signed_in.post("/api/boards", json={"name": "Outfit"}).json()
    item_id = make_item(signed_in, "Coat")
    signed_in.put(
        f"/api/boards/{board['id']}/placements",
        json={"placements": [{"item_id": item_id, "position_x": 0, "position_y": 0}]},
    )

    signed_in.put(f"/api/boards/{board['id']}/placements", json={"placements": []})

    assert signed_in.get(f"/api/items/{item_id}").status_code == 200


def test_deleting_an_item_removes_it_from_boards_and_the_board_still_opens(signed_in):
    board = signed_in.post("/api/boards", json={"name": "Outfit"}).json()
    kept, doomed = make_item(signed_in, "Coat"), make_item(signed_in, "Hat")
    signed_in.put(
        f"/api/boards/{board['id']}/placements",
        json={
            "placements": [
                {"item_id": kept, "position_x": 0, "position_y": 0},
                {"item_id": doomed, "position_x": 10, "position_y": 10},
            ]
        },
    )

    assert signed_in.delete(f"/api/items/{doomed}").status_code == 204

    reopened = signed_in.get(f"/api/boards/{board['id']}")
    assert reopened.status_code == 200
    assert [p["item"]["id"] for p in reopened.json()["placements"]] == [kept]


def test_deleting_a_board_never_touches_the_items_on_it(signed_in):
    board = signed_in.post("/api/boards", json={"name": "Outfit"}).json()
    item_id = make_item(signed_in, "Coat")
    signed_in.put(
        f"/api/boards/{board['id']}/placements",
        json={"placements": [{"item_id": item_id, "position_x": 0, "position_y": 0}]},
    )

    assert signed_in.delete(f"/api/boards/{board['id']}").status_code == 204

    assert signed_in.get(f"/api/items/{item_id}").status_code == 200


def test_placing_an_item_that_no_longer_exists_is_refused(signed_in):
    board = signed_in.post("/api/boards", json={"name": "Outfit"}).json()

    response = signed_in.put(
        f"/api/boards/{board['id']}/placements",
        json={"placements": [{"item_id": "gone", "position_x": 0, "position_y": 0}]},
    )

    assert response.status_code == 400


def test_a_zero_or_negative_scale_is_refused(signed_in):
    board = signed_in.post("/api/boards", json={"name": "Outfit"}).json()
    item_id = make_item(signed_in, "Coat")

    response = signed_in.put(
        f"/api/boards/{board['id']}/placements",
        json={"placements": [{"item_id": item_id, "position_x": 0, "position_y": 0, "scale": 0}]},
    )

    assert response.status_code == 422


def test_the_board_list_shows_a_cover_and_a_count(signed_in):
    board = signed_in.post("/api/boards", json={"name": "Outfit"}).json()
    item_id = make_item(signed_in, "Coat")
    signed_in.put(
        f"/api/boards/{board['id']}/placements",
        json={"placements": [{"item_id": item_id, "position_x": 0, "position_y": 0}]},
    )

    listed = signed_in.get("/api/boards").json()

    assert listed[0]["item_count"] == 1
    assert listed[0]["name"] == "Outfit"
