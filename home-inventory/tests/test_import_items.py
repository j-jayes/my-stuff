"""Bulk import of reviewed purchases through the real API."""

import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import PASSWORD

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import import_items


def candidate(**overrides) -> dict:
    return {
        "shop": "Zalando",
        "order": "11111063435993",
        "line": 2,
        "date": "2025-11-28",
        "brand": "Clarks Originals",
        "name": "Lace-ups - black",
        "size": "46",
        "qty": 1,
        "price": 1073,
        "currency": "SEK",
        "second_hand": False,
        "image_url": None,
        "category": "Shoes",
        "room": "Closet",
    } | overrides


def details(client) -> list[dict]:
    summaries = client.get("/api/items", params={"limit": 200}).json()["items"]
    return [client.get(f"/api/items/{s['id']}").json() for s in summaries]


def test_creates_the_item_with_every_field_the_email_gave(signed_in, rooms, categories):
    link = "https://www.ikea.com/se/en/p/trofast-storage-box-bright-green-40582096/"
    result = import_items.run(
        signed_in, [candidate(price=59.5, source_url=link)], log=lambda _: None
    )

    assert result["created"] == 1
    item = details(signed_in)[0]
    assert item["source_url"] == link
    assert item["name"] == "Lace-ups - black"
    assert item["brand"] == "Clarks Originals"
    assert item["purchase_price_minor"] == 5950
    assert item["currency"] == "SEK"
    assert item["quantity"] == 1
    assert item["purchase_date"] == "2025-11-28"
    assert item["second_hand"] is False
    assert item["descriptor_notes"] == "Size 46. Zalando order 11111063435993, line 2."
    assert item["category"]["id"] == categories["Shoes"]
    assert item["room"]["id"] == rooms["Closet"]


def test_an_item_without_a_size_or_room_still_imports(signed_in):
    item = candidate(size=None, room=None, category="Electronics", brand=None, qty=3)

    import_items.run(signed_in, [item], log=lambda _: None)

    created = details(signed_in)[0]
    assert created["descriptor_notes"] == "Zalando order 11111063435993, line 2."
    assert created["room"] is None
    assert created["quantity"] == 3


def test_running_it_twice_creates_nothing_new(signed_in):
    items = [candidate(), candidate(line=1, size="45")]

    import_items.run(signed_in, items, log=lambda _: None)
    second = import_items.run(signed_in, items, log=lambda _: None)

    assert second == {"created": 0, "skipped": 2, "no_photo": []}
    assert len(details(signed_in)) == 2


def test_line_one_is_not_mistaken_for_line_ten(signed_in):
    import_items.run(signed_in, [candidate(line=10)], log=lambda _: None)

    result = import_items.run(signed_in, [candidate(line=1)], log=lambda _: None)

    assert result["created"] == 1


def test_a_dry_run_writes_nothing(signed_in):
    result = import_items.run(signed_in, [candidate()], dry_run=True, log=lambda _: None)

    assert result["created"] == 1
    assert details(signed_in) == []


def test_an_unreachable_photo_keeps_the_item_and_reports_it(client, monkeypatch):
    async def refused(*_args, **_kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr("app.routers.items.download_image", refused)
    # A real deployment answers 500 here; the default test client would re-raise instead.
    lenient = TestClient(app, raise_server_exceptions=False)
    import_items.login(lenient, PASSWORD)

    result = import_items.run(
        lenient, [candidate(image_url="https://example.com/a.jpg")], log=lambda _: None
    )

    assert result["created"] == 1
    assert result["no_photo"] == ["Clarks Originals Lace-ups - black"]
    assert details(lenient)[0]["image_url"] is None


def test_a_wrong_password_stops_with_a_clear_message(client):
    with pytest.raises(SystemExit, match="password"):
        import_items.login(client, "wrong")


def test_an_unknown_category_stops_before_anything_is_written(signed_in):
    items = [candidate(), candidate(line=1, category="Nonsense")]

    with pytest.raises(SystemExit, match="Nonsense"):
        import_items.run(signed_in, items, log=lambda _: None)

    assert details(signed_in) == []
