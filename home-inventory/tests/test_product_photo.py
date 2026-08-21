"""Turning the owner's photograph into a product shot of the same thing.

The generated image is a proposal, not a fact: it is written to storage and shown, and only
replaces the photograph when the owner says so (constitution principle III). The photograph
they took is kept either way — it is the evidence that they own the thing.

The model is stubbed throughout. What matters here is that nothing is overwritten before it
is accepted, and that nothing is left behind afterwards.
"""

import io
import json

import pytest
from PIL import Image

from app.extract import ExtractionUnavailable


def create(client, photo=None, **fields):
    payload = {"name": "Ochre cotton jacket", **fields}
    files = {"image": ("photo.png", photo, "image/png")} if photo else None
    response = client.post("/api/items", data={"payload": json.dumps(payload)}, files=files)
    assert response.status_code == 201, response.text
    return response.json()


def generated_png() -> bytes:
    """A real image, so the thumbnail is really made from it rather than stubbed."""
    buffer = io.BytesIO()
    Image.new("RGB", (600, 900), (200, 140, 40)).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def generator(monkeypatch):
    """Records what it was asked for and hands back a fixed image."""
    calls: list[dict] = []

    def fake(settings, *, image, content_type, name):
        calls.append({"image": image, "content_type": content_type, "name": name})
        return generated_png(), "image/png"

    monkeypatch.setattr("app.routers.items.generate_product_photo", fake)
    return calls


def test_a_preview_is_offered_without_touching_the_photograph(signed_in, photo, generator):
    item = create(signed_in, photo=photo)

    response = signed_in.post(f"/api/items/{item['id']}/product-photo")

    assert response.status_code == 200
    preview_url = response.json()["preview_url"]
    assert signed_in.get(preview_url).status_code == 200
    # Nothing about the item has changed yet: this is a proposal.
    after = signed_in.get(f"/api/items/{item['id']}").json()
    assert after["image_url"] == item["image_url"]
    assert after["thumb_url"] == item["thumb_url"]


def test_the_item_is_named_so_the_model_knows_which_thing_it_is_looking_at(
    signed_in, photo, generator
):
    item = create(signed_in, photo=photo, name="Oxford shirt, blue")

    signed_in.post(f"/api/items/{item['id']}/product-photo")

    assert generator[0]["name"] == "Oxford shirt, blue"
    assert generator[0]["image"] == photo


def test_there_is_nothing_to_work_from_without_a_photograph(signed_in, generator):
    item = create(signed_in)

    response = signed_in.post(f"/api/items/{item['id']}/product-photo")

    assert response.status_code == 400
    assert generator == []


def test_an_item_that_does_not_exist_is_a_404(signed_in, generator):
    assert signed_in.post("/api/items/nope/product-photo").status_code == 404


def test_a_model_that_will_not_answer_is_reported_not_swallowed(signed_in, photo, monkeypatch):
    def boom(*args, **kwargs):
        raise ExtractionUnavailable("no quota")

    monkeypatch.setattr("app.routers.items.generate_product_photo", boom)
    item = create(signed_in, photo=photo)

    assert signed_in.post(f"/api/items/{item['id']}/product-photo").status_code == 502


def test_accepting_a_preview_makes_it_the_photo_and_keeps_the_original(
    signed_in, photo, generator
):
    item = create(signed_in, photo=photo)
    signed_in.post(f"/api/items/{item['id']}/product-photo")

    response = signed_in.post(f"/api/items/{item['id']}/product-photo/accept")

    assert response.status_code == 200
    accepted = response.json()
    # The generated image is now the item's photo, with a thumbnail made from it.
    assert signed_in.get(accepted["image_url"]).content == generated_png()
    assert signed_in.get(accepted["thumb_url"]).headers["content-type"] == "image/webp"
    # The photograph the owner took is still there, under its own name.
    assert accepted["source_photo_url"]
    assert signed_in.get(accepted["source_photo_url"]).content == photo


def test_the_new_photo_does_not_hide_behind_the_cached_old_one(signed_in, photo, generator):
    """Media is served immutable for a year and a thumbnail always lands on the same key, so
    without something in the URL that changes, every grid tile keeps showing the old picture.

    What changes it is the item's updated_at, which accepting a photo bumps. The listing and
    the detail have to agree on it, or the grid and the item page show different pictures.
    """
    item = create(signed_in, photo=photo)
    signed_in.post(f"/api/items/{item['id']}/product-photo")

    accepted = signed_in.post(f"/api/items/{item['id']}/product-photo/accept").json()

    assert accepted["thumb_url"].endswith(f"?v={accepted['updated_at']}")
    assert signed_in.get(accepted["thumb_url"]).status_code == 200
    listed = signed_in.get("/api/items").json()["items"]
    assert [i["thumb_url"] for i in listed] == [accepted["thumb_url"]]


def test_a_picture_that_changes_gets_an_address_that_changes(local_storage):
    """The serialiser's half of it, without racing the one-second clock the timestamps use."""
    from app.deps import to_summary
    from app.models import Item

    def jacket(updated_at: str) -> Item:
        return Item(
            id="i",
            name="Jacket",
            thumb_key="items/i/thumb.webp",
            quantity=1,
            created_at="2026-08-21T10:00:00Z",
            updated_at=updated_at,
        )

    before, after = jacket("2026-08-21T10:00:00Z"), jacket("2026-08-21T10:00:31Z")

    # Same key, same stored object — a different address, so the browser fetches it again.
    assert to_summary(before).thumb_url != to_summary(after).thumb_url


def test_the_preview_does_not_outlive_being_accepted(signed_in, photo, generator):
    item = create(signed_in, photo=photo)
    preview_url = signed_in.post(f"/api/items/{item['id']}/product-photo").json()["preview_url"]

    signed_in.post(f"/api/items/{item['id']}/product-photo/accept")

    assert signed_in.get(preview_url).status_code == 404


def test_accepting_something_that_was_never_generated_is_refused(signed_in, photo, generator):
    item = create(signed_in, photo=photo)

    response = signed_in.post(f"/api/items/{item['id']}/product-photo/accept")

    assert response.status_code == 409


def test_discarding_is_just_not_accepting(signed_in, photo, generator):
    """There is no discard endpoint. The preview is overwritten by the next generation and
    removed when the item is, so an unaccepted one costs one object and nothing else."""
    item = create(signed_in, photo=photo)
    signed_in.post(f"/api/items/{item['id']}/product-photo")

    after = signed_in.get(f"/api/items/{item['id']}").json()

    assert after["image_url"] == item["image_url"]
    assert after["source_photo_url"] is None


def test_deleting_the_item_takes_every_image_with_it(signed_in, photo, generator, local_storage):
    item = create(signed_in, photo=photo)
    signed_in.post(f"/api/items/{item['id']}/product-photo")
    accepted = signed_in.post(f"/api/items/{item['id']}/product-photo/accept").json()
    # Generated again, so there is an unaccepted preview lying about at deletion time too.
    signed_in.post(f"/api/items/{item['id']}/product-photo")

    assert signed_in.delete(f"/api/items/{item['id']}").status_code == 204

    for url in (accepted["image_url"], accepted["thumb_url"], accepted["source_photo_url"]):
        assert signed_in.get(url).status_code == 404
    assert list((local_storage._root / "items" / item["id"]).glob("*")) == []
