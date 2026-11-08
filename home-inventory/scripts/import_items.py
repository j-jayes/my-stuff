"""Add a reviewed list of purchases to the inventory through its API.

The API rather than the database file, because every write has to go through the snapshot the
running service holds. Safe to re-run: each item's order and line are written into its notes,
and an item whose reference is already there is skipped.

    INVENTORY_PASSWORD=... uv run python scripts/import_items.py approved.json \
        --base-url https://my-stuff-716260291301.europe-north1.run.app [--dry-run]

approved.json is a list of objects with: shop, order, line, date, brand, name, size, qty, price
(per unit, as paid), currency, second_hand, image_url, source_url, category, room. Names of category and room
must match the ones already in the app.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx

PAGE_SIZE = 200


def login(client: httpx.Client, password: str) -> None:
    response = client.post("/api/auth/login", json={"password": password})
    if response.status_code != 204:
        raise SystemExit(
            f"Login failed ({response.status_code}): is the password in INVENTORY_PASSWORD right?"
        )


def _reference(item: dict) -> str:
    """What marks an item as imported. `ref` is for things with no order to point at."""
    return item.get("ref") or f"{item['shop']} order {item['order']}, line {item['line']}."


def _notes(item: dict) -> str:
    size = f"Size {item['size']}. " if item.get("size") else ""
    extra = f"{item['notes']} " if item.get("notes") else ""
    return size + extra + _reference(item)


def _ids_by_name(client: httpx.Client, path: str) -> dict[str, str]:
    response = client.get(path)
    response.raise_for_status()
    return {row["name"]: row["id"] for row in response.json()}


def all_details(client: httpx.Client) -> list[dict]:
    """Every item in full, gifts included, or a re-run would import a gift a second time.

    Notes are only on the detail view, not on the list.
    """
    details = []
    for gifted in ("false", "true"):
        offset = 0
        while True:
            params = {"limit": PAGE_SIZE, "offset": offset, "gifted": gifted}
            response = client.get("/api/items", params=params)
            response.raise_for_status()
            page = response.json()
            for summary in page["items"]:
                detail = client.get(f"/api/items/{summary['id']}")
                detail.raise_for_status()
                details.append(detail.json())
            offset += PAGE_SIZE
            if offset >= page["total"]:
                break
    return details


def _existing_notes(client: httpx.Client) -> list[str]:
    return [detail["descriptor_notes"] or "" for detail in all_details(client)]


def _payload(item: dict, categories: dict[str, str], rooms: dict[str, str]) -> dict:
    payload = {
        "name": item["name"],
        "brand": item.get("brand"),
        "descriptor_notes": _notes(item),
        "quantity": item.get("qty") or 1,
        "second_hand": item["second_hand"],
        "purchase_date": item.get("date"),
        "source_url": item.get("source_url"),
        "category_id": categories[item["category"]],
        "room_id": rooms[item["room"]] if item.get("room") else None,
    }
    if item.get("price") is not None:
        payload["purchase_price_minor"] = round(item["price"] * 100)
        payload["currency"] = item["currency"]
    return payload


def _post(client: httpx.Client, payload: dict) -> httpx.Response:
    return client.post("/api/items", data={"payload": json.dumps(payload)})


def _label(item: dict) -> str:
    return " ".join(filter(None, [item.get("brand"), item["name"]]))


def run(
    client: httpx.Client,
    items: list[dict],
    dry_run: bool = False,
    log: Callable[[str], None] = print,
) -> dict:
    categories = _ids_by_name(client, "/api/categories")
    rooms = _ids_by_name(client, "/api/rooms")
    for item in items:
        if item["category"] not in categories:
            raise SystemExit(f"Unknown category {item['category']!r} on {_label(item)}")
        if item.get("room") and item["room"] not in rooms:
            raise SystemExit(f"Unknown room {item['room']!r} on {_label(item)}")

    existing = _existing_notes(client)
    result = {"created": 0, "skipped": 0, "no_photo": []}
    for item in items:
        if any(_reference(item) in note for note in existing):
            result["skipped"] += 1
            log(f"skip    {_label(item)}")
            continue
        if not dry_run:
            payload = _payload(item, categories, rooms)
            if item.get("image_url"):
                response = _post(client, payload | {"source_image_url": item["image_url"]})
                if not response.is_success:
                    # Nothing was saved: the photo is fetched before the row is written.
                    log(f"photo failed ({response.status_code}), adding without it")
                    result["no_photo"].append(_label(item))
                    response = _post(client, payload)
            else:
                response = _post(client, payload)
            if response.status_code != 201:
                raise SystemExit(
                    f"Stopped at {_label(item)}: {response.status_code} {response.text}. "
                    "Items before it were saved; re-running skips them."
                )
            if "gift_to" in item:
                client.post(
                    f"/api/items/{response.json()['id']}/gift", json={"to": item["gift_to"]}
                ).raise_for_status()
        result["created"] += 1
        log(f"{'would add' if dry_run else 'added'}   {_label(item)}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("items", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    password = os.environ.get("INVENTORY_PASSWORD")
    if not password:
        sys.exit("Set INVENTORY_PASSWORD first")
    items = json.loads(args.items.read_text())
    # Long enough for a cold start plus a photo download.
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        login(client, password)
        result = run(client, items, dry_run=args.dry_run)
    print(f"\n{result['created']} added, {result['skipped']} already there")
    if result["no_photo"]:
        print("Added without a photo:\n  " + "\n  ".join(result["no_photo"]))


if __name__ == "__main__":
    main()
