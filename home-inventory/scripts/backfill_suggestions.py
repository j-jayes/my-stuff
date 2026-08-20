"""Re-run the new extraction over items that were added before it existed, and report what it
would change. This writes nothing — not to the database, not to storage.

The seven scraped items in the live inventory carry the old scraper's output: names that are
raw page titles ("IVAR shelving unit, with 6 shelves/pine, 89x50x226 cm  - IKEA Sweden"), no
prices at all, and at least one where the product name ended up in the brand field. This
proposes fixes for a human to read.

    uv run python scripts/backfill_suggestions.py --db /tmp/copy.sqlite --out proposals.json

Take a copy of the database first; pointing this at the live file is unnecessary, since it
only ever reads, but a copy makes that obvious.
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.extract import ExtractionUnavailable, _to_minor, resolve_name, suggest_item
from app.scrape import fetch_page_metadata

FIELDS = ("name", "brand", "descriptor_notes", "purchase_price_minor", "currency", "quantity")


def _read(db_path: str) -> tuple[list[sqlite3.Row], list[str], list[str], list[str]]:
    """Everything needed, in one read-only pass. The connection is opened read-only so a
    mistake cannot become a write."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        items = connection.execute(
            "SELECT i.*, c.name AS category_name, r.name AS room_name FROM items i"
            " LEFT JOIN categories c ON c.id = i.category_id"
            " LEFT JOIN rooms r ON r.id = i.room_id"
            " WHERE i.source_url IS NOT NULL AND i.source_url != ''"
            " ORDER BY i.created_at"
        ).fetchall()
        tops = [r[0] for r in connection.execute(
            "SELECT name FROM categories WHERE parent_id IS NULL ORDER BY sort_order"
        )]
        shelves = [r[0] for r in connection.execute(
            "SELECT name FROM categories WHERE parent_id IS NOT NULL ORDER BY sort_order"
        )]
        rooms = [r[0] for r in connection.execute("SELECT name FROM rooms ORDER BY sort_order")]
    finally:
        connection.close()
    return items, tops, shelves, rooms


async def _propose(item: sqlite3.Row, settings: Settings, tops, shelves, rooms) -> dict:
    proposal: dict = {"id": item["id"], "source_url": item["source_url"]}
    try:
        page = await fetch_page_metadata(item["source_url"], settings.scrape_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - a page that will not load is a skip, not a crash
        return {**proposal, "error": f"could not fetch: {exc}"}

    try:
        suggestion = suggest_item(
            settings, categories=tops, subcategories=shelves, rooms=rooms, page=page.digest
        )
    except ExtractionUnavailable as exc:
        return {**proposal, "error": f"could not extract: {exc}"}

    proposed = {
        "name": suggestion.name,
        "brand": suggestion.brand,
        "descriptor_notes": suggestion.descriptor_notes,
        "purchase_price_minor": _to_minor(suggestion.price),
        "currency": suggestion.currency,
        "quantity": suggestion.quantity,
        # Resolved the same way the API resolves it, so the report shows what would actually
        # be stored rather than whatever the model happened to say. It has offered "Symaskin"
        # and "Armchairs" for these very items, and neither is a category.
        "category": resolve_name(shelves, suggestion.subcategory)
        or resolve_name(tops, suggestion.category),
        "room": resolve_name(rooms, suggestion.room),
    }
    current = {field: item[field] for field in FIELDS}
    current["category"] = item["category_name"]
    current["room"] = item["room_name"]
    return {
        **proposal,
        "current": current,
        "proposed": proposed,
        "changes": sorted(k for k, v in proposed.items() if v and v != current.get(k)),
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="path to a copy of the database")
    parser.add_argument("--out", help="write JSON here instead of stdout")
    args = parser.parse_args()

    items, tops, shelves, rooms = _read(args.db)
    print(f"{len(items)} items have a source_url", file=sys.stderr)

    proposals = []
    for item in items:
        proposal = await _propose(item, Settings(), tops, shelves, rooms)
        proposals.append(proposal)
        if "error" in proposal:
            print(f"  ! {item['name'][:50]}: {proposal['error']}", file=sys.stderr)
        else:
            print(f"  · {item['name'][:50]} -> {', '.join(proposal['changes']) or 'no change'}",
                  file=sys.stderr)

    report = json.dumps(proposals, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(report)
        print(f"\nWritten to {args.out}. Nothing has been changed.", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
