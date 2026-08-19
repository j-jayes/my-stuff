# Data Model: Home Inventory

**Store**: SQLite, one file, one writer. Accessed through SQLAlchemy 2.0 ORM. Schema changes
are applied by Alembic migrations.

All primary keys are UUIDv4 stored as `TEXT`. All timestamps are UTC, stored as ISO-8601 `TEXT`.
Money is stored as `INTEGER` minor units (öre/cents) to avoid float rounding, together with a
3-letter currency code — never as `REAL`.

## Tables

### `rooms`

| column | type | constraints |
|---|---|---|
| `id` | TEXT | PK |
| `name` | TEXT | NOT NULL, UNIQUE (case-insensitive) |
| `sort_order` | INTEGER | NOT NULL, default 0 |
| `created_at` | TEXT | NOT NULL |

Seeded with: Kitchen, Bedroom, Lounge, Bathroom, Storage Room.

### `categories`

Same shape as `rooms`. Seeded with: Furniture, Electronics, Major Appliances, Small Appliances,
Kitchenware, Tools, Decor, Clothing & Accessories, Miscellaneous.

### `items`

| column | type | constraints |
|---|---|---|
| `id` | TEXT | PK |
| `name` | TEXT | NOT NULL, non-empty after strip |
| `brand` | TEXT | nullable |
| `descriptor_notes` | TEXT | nullable |
| `purchase_price_minor` | INTEGER | nullable, `>= 0` |
| `currency` | TEXT | nullable, 3 chars, required when price is set |
| `purchase_date` | TEXT | nullable, `YYYY-MM-DD` |
| `serial_number` | TEXT | nullable |
| `source_url` | TEXT | nullable |
| `image_key` | TEXT | nullable — GCS object key of the full-size photo |
| `thumb_key` | TEXT | nullable — GCS object key of the generated thumbnail |
| `receipt_key` | TEXT | nullable — GCS object key of the receipt image |
| `room_id` | TEXT | nullable, FK → `rooms.id` ON DELETE RESTRICT |
| `category_id` | TEXT | nullable, FK → `categories.id` ON DELETE RESTRICT |
| `ai_suggested_fields` | TEXT | nullable — JSON array of field names the model filled and the owner did not change |
| `created_at` | TEXT | NOT NULL |
| `updated_at` | TEXT | NOT NULL |

Indexes: `room_id`, `category_id`, `created_at DESC`.

`ON DELETE RESTRICT` on `room_id`/`category_id` is what enforces FR-015 (a room in use cannot
be deleted). `ai_suggested_fields` exists only so the UI can keep marking untouched values as
suggestions after a reload; it carries no behaviour.

### `items_fts`

SQLite FTS5 virtual table over `items(name, brand, descriptor_notes)`, kept in sync by triggers,
backing the search in FR-013. With a few thousand rows a `LIKE` scan would also work; FTS5 is
used because it is built into SQLite and needs no extra dependency.

### `boards`

| column | type | constraints |
|---|---|---|
| `id` | TEXT | PK |
| `name` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |
| `updated_at` | TEXT | NOT NULL |

### `board_items`

| column | type | constraints |
|---|---|---|
| `id` | TEXT | PK |
| `board_id` | TEXT | NOT NULL, FK → `boards.id` ON DELETE CASCADE |
| `item_id` | TEXT | NOT NULL, FK → `items.id` ON DELETE CASCADE |
| `position_x` | REAL | NOT NULL |
| `position_y` | REAL | NOT NULL |
| `scale` | REAL | NOT NULL, default 1.0, `> 0` |
| `z_index` | INTEGER | NOT NULL, default 0 |

Unique on `(board_id, item_id)` — an item appears at most once per board. Cascade from `items`
is what satisfies FR-019 (deleting an item removes its placements). Coordinates are stored in
**canvas units**, not pixels, so a board laid out on a laptop reopens correctly on a phone: the
canvas is a fixed 1000 × 1000 unit space that the client scales to the viewport.

## Relationships

```
rooms 1 ──< items >── 1 categories
boards 1 ──< board_items >── 1 items
```

## Validation rules

Enforced in Pydantic request models, and mirrored as SQLite CHECK constraints where cheap:

- `name` is required and must be non-empty after stripping (FR-009).
- `purchase_price_minor >= 0`; `currency` must be present whenever a price is present.
- `purchase_date` must parse as a date and must not be in the future.
- `scale > 0`.
- Room and category names are unique case-insensitively.
- A room or category referenced by any item cannot be deleted; the API returns 409 with the
  count of items blocking it.

## Object storage layout

One private GCS bucket, keys namespaced by kind and item id:

```
items/{item_id}/original.{ext}
items/{item_id}/thumb.jpg
items/{item_id}/receipt.{ext}
```

The database stores keys, never URLs, so the bucket can be renamed or moved without a data
migration.
