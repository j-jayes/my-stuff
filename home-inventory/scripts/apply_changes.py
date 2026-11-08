"""Create rooms, add items and correct existing items from one JSON file, through the API.

    INVENTORY_PASSWORD=... uv run python scripts/apply_changes.py changes.json \
        --base-url https://my-stuff-716260291301.europe-north1.run.app

changes.json has any of:
    rooms      names to create if they are not there yet
    categories categories to create if they are not there yet: a name, or {"name", "parent"} to
               put one inside another (parents first)
    new_items  as for import_items.py; `ref` and `notes` replace the order for things without one,
               and `gift_to` (a name, or null) records the item as already given away
    updates    a selector (item `id`, `ref` in the notes, exact `name`, or `name_contains`, with `many: true`
               if it may match several) plus any of `room`, `category`, `quantity`, `price` with `currency`,
               `source_url`, `image_url` (a photo that cannot be fetched is reported and skipped),
               or `gift: true` with an optional `gift_to`

Every selector is checked before anything is written, and the whole file is safe to re-run.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
from import_items import _ids_by_name, all_details, login
from import_items import run as import_new


def _select(update: dict, items: list[dict]) -> list[dict]:
    if "id" in update:
        wanted, found = update["id"], [i for i in items if i["id"] == update["id"]]
    elif "ref" in update:
        wanted, found = (
            update["ref"],
            [i for i in items if update["ref"] in (i["descriptor_notes"] or "")],
        )
    elif "name" in update:
        wanted, found = update["name"], [i for i in items if i["name"] == update["name"]]
    else:
        wanted, found = (
            update["name_contains"],
            [i for i in items if update["name_contains"] in i["name"]],
        )
    if not found:
        raise SystemExit(f"Nothing matches {wanted!r}. Nothing was changed.")
    if len(found) > 1 and not update.get("many"):
        raise SystemExit(f"{len(found)} items match {wanted!r}. Nothing was changed.")
    return found


def _rooms(client: httpx.Client) -> dict[str, str]:
    response = client.get("/api/rooms")
    response.raise_for_status()
    return {room["name"]: room["id"] for room in response.json()}


def run(client: httpx.Client, changes: dict, log: Callable[[str], None] = print) -> None:
    items = all_details(client)
    targets = [(update, _select(update, items)) for update in changes.get("updates", [])]

    wanted_categories = [
        {"name": c} if isinstance(c, str) else c for c in changes.get("categories", [])
    ]
    known = _ids_by_name(client, "/api/categories")
    for update, _ in targets:
        if "category" in update and update["category"] not in {
            *known,
            *(c["name"] for c in wanted_categories),
        }:
            raise SystemExit(f"Unknown category {update['category']!r}. Nothing was changed.")

    existing = _rooms(client)
    for name in changes.get("rooms", []):
        if name not in existing:
            client.post("/api/rooms", json={"name": name}).raise_for_status()
            log(f"room    {name}")
    rooms = _rooms(client)

    for category in wanted_categories:
        if category["name"] not in known:
            parent = category.get("parent")
            client.post(
                "/api/categories",
                json={"name": category["name"], "parent_id": known[parent] if parent else None},
            ).raise_for_status()
            known = _ids_by_name(client, "/api/categories")
            log(f"category {category['name']}")
    categories = known

    if changes.get("new_items"):
        import_new(client, changes["new_items"], log=log)

    for update, found in targets:
        payload = {}
        if "price" in update:
            payload["purchase_price_minor"] = round(update["price"] * 100)
            payload["currency"] = update["currency"]
        if "room" in update:
            if update["room"] not in rooms:
                raise SystemExit(f"Unknown room {update['room']!r}")
            payload["room_id"] = rooms[update["room"]]
        if "category" in update:
            payload["category_id"] = categories[update["category"]]
        if "quantity" in update:
            payload["quantity"] = update["quantity"]
        if "source_url" in update:
            payload["source_url"] = update["source_url"]
        for item in found:
            if payload:
                response = client.patch(
                    f"/api/items/{item['id']}", data={"payload": json.dumps(payload)}
                )
                if response.status_code != 200:
                    raise SystemExit(
                        f"Stopped at {item['name']}: {response.status_code} {response.text}"
                    )
            if "image_url" in update:
                photo = client.patch(
                    f"/api/items/{item['id']}",
                    data={"payload": json.dumps({"source_image_url": update["image_url"]})},
                )
                if photo.status_code != 200:
                    log(f"no photo {item['name']}: {photo.status_code}")
            if update.get("gift"):
                client.post(
                    f"/api/items/{item['id']}/gift", json={"to": update.get("gift_to")}
                ).raise_for_status()
            log(f"update  {item['name']}: {sorted(set(update) - {'id', 'ref', 'name', 'many'})}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("changes", type=Path)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    password = os.environ.get("INVENTORY_PASSWORD")
    if not password:
        sys.exit("Set INVENTORY_PASSWORD first")
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        login(client, password)
        run(client, json.loads(args.changes.read_text()))


if __name__ == "__main__":
    main()
