"""Create rooms, add items and correct existing items from one JSON file, through the API.

    INVENTORY_PASSWORD=... uv run python scripts/apply_changes.py changes.json \
        --base-url https://my-stuff-716260291301.europe-north1.run.app

changes.json has any of:
    rooms      names to create if they are not there yet
    new_items  as for import_items.py; `ref` and `notes` replace the order for things without one
    updates    a selector (`ref` in the notes, exact `name`, or `name_contains`, with `many: true`
               if it may match several) plus `room` and/or `quantity`

Every selector is checked before anything is written, and the whole file is safe to re-run.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
from import_items import all_details, login
from import_items import run as import_new


def _select(update: dict, items: list[dict]) -> list[dict]:
    if "ref" in update:
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

    existing = _rooms(client)
    for name in changes.get("rooms", []):
        if name not in existing:
            client.post("/api/rooms", json={"name": name}).raise_for_status()
            log(f"room    {name}")
    rooms = _rooms(client)

    if changes.get("new_items"):
        import_new(client, changes["new_items"], log=log)

    for update, found in targets:
        payload = {}
        if "room" in update:
            if update["room"] not in rooms:
                raise SystemExit(f"Unknown room {update['room']!r}")
            payload["room_id"] = rooms[update["room"]]
        if "quantity" in update:
            payload["quantity"] = update["quantity"]
        for item in found:
            response = client.patch(
                f"/api/items/{item['id']}", data={"payload": json.dumps(payload)}
            )
            if response.status_code != 200:
                raise SystemExit(
                    f"Stopped at {item['name']}: {response.status_code} {response.text}"
                )
            log(
                f"update  {item['name']}: {update.get('room') or ''} {update.get('quantity') or ''}"
            )


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
