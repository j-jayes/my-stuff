# API Contract: Home Inventory

All paths are under `/api`. Everything except `POST /api/auth/login` and `GET /api/health`
requires a valid session cookie; without one the server returns **401** and an empty body
(FR-020).

Errors use a single shape:

```json
{ "detail": "Human-readable message" }
```

Status codes used: 200, 201, 204, 400 (validation), 401 (no session), 404, 409 (conflict, e.g.
deleting a room still in use), 413 (upload too large), 502 (upstream fetch or model failure),
504 (upstream timeout).

## Auth

### `POST /api/auth/login`

```json
// request
{ "password": "…" }
// 204 No Content + Set-Cookie: session=…; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000
```

Wrong password → **401**, message `"Incorrect password"` with no further detail (FR-021).
Rate-limited to 10 attempts per minute per IP.

### `POST /api/auth/logout`

**204**, clears the cookie.

### `GET /api/auth/me`

**200** `{ "authenticated": true }` — used by the frontend on load to decide whether to show
the password screen.

## Items

### `GET /api/items`

Query parameters, all optional and combinable (FR-012):

| param | type | meaning |
|---|---|---|
| `q` | string | full-text search over name, brand, notes |
| `room_id` | uuid | filter to one room |
| `category_id` | uuid | filter to one category |
| `limit` | int | default 50, max 200 |
| `offset` | int | default 0 |

```json
// 200
{
  "items": [
    {
      "id": "…", "name": "Ercol Windsor chair", "brand": "Ercol",
      "thumb_url": "https://…", "room": {"id": "…", "name": "Lounge"},
      "category": {"id": "…", "name": "Furniture"}, "created_at": "2026-08-19T10:00:00Z"
    }
  ],
  "total": 137
}
```

List responses carry `thumb_url` only — never the full-size image (FR-023).

### `GET /api/items/{id}`

**200** with the full record: every column from `data-model.md`, plus `image_url`,
`thumb_url`, `receipt_url` (short-lived URLs), plus `ai_suggested_fields`.

### `POST /api/items`

`multipart/form-data`:

| part | required | notes |
|---|---|---|
| `payload` | yes | JSON blob of the item fields |
| `image` | no | the item photo |
| `receipt` | no | the receipt photo |

`payload`:

```json
{
  "name": "Ercol Windsor chair",
  "brand": "Ercol",
  "descriptor_notes": "Elm seat, beech legs, mid-century",
  "purchase_price_minor": 450000,
  "currency": "SEK",
  "quantity": 1,
  "purchase_date": "2024-03-11",
  "serial_number": null,
  "source_url": null,
  "room_id": "…",
  "category_id": "…",
  "ai_suggested_fields": ["name", "brand", "descriptor_notes"]
}
```

`quantity` is how many of the thing the row stands for, and defaults to 1;
`purchase_price_minor` is the price of **one** of them. A `PATCH` that does not mention
`quantity` leaves it alone, like every other field.

**201** with the same body as `GET /api/items/{id}`. Uploads over 20 MB → **413**.

### `PATCH /api/items/{id}`

Same multipart shape; every field optional; only supplied fields change. Sending a new `image`
replaces the stored photo and regenerates the thumbnail; the old objects are deleted.
**200** with the updated record.

### `DELETE /api/items/{id}`

**204**. Deletes the row, its GCS objects, and its board placements (FR-019).

## Capture helpers

### `POST /api/items/suggest`

`multipart/form-data` with any combination of `image`, `url` and `note` — at least one, or
**400**. One endpoint rather than three, because they are the same question asked with
different evidence, and the owner can supply more than one at a time. Returns a filled-in
form **without creating anything** (FR-002).

```json
// 200
{
  "name": "01 Kitchen Spoon",
  "brand": "Gestura",
  "descriptor_notes": "Mirror-finish 18/10 stainless steel cooking spoon made in Japan.",
  "category_id": "…", "room_id": "…",
  "purchase_price_minor": 44500, "currency": "SEK",
  "purchase_date": "2025-06-01", "quantity": 6,
  "source_url": "https://…", "image_url": "https://…",
  "suggested_fields": ["name", "brand", "category", "room", "price", "quantity"]
}
```

Ids, not names, so the client can drop them straight into its selects. `suggested_fields`
names what the model filled, so the form can badge those as guesses.

When `url` is given, the page is fetched server-side and reduced to a digest — meta tags, any
`schema.org` JSON-LD, and the visible text — which is what the model reads. That digest is
untrusted third-party text: it is fenced and labelled as data in the prompt, the fields it
could steer are constrained to the owner's own lists, and the result only ever pre-fills an
editable form.

Prices come back from the model as printed (`"1995"`) and are converted to minor units in
Python. Asking the model for minor units would be asking it to multiply by 100 on every
extraction, where a 100× error is silent and plausible.

Category, subcategory and room are **resolved** against the owner's lists case-insensitively,
and anything unrecognised is dropped — the JSON-schema `enum` steers the model but does not
bind it. A subcategory that does not exist falls back to the top-level category.

Model failure → **502**, model timeout (8s) → **504**, page timeout (6s) → **504**. If a page
was fetched but the model is unavailable, the response is **200** carrying `og:title` and
`og:image` instead — the old behaviour, so the link path is never worse than it was. A page
with no image is **200** with `image_url: null` (US3 scenario 3).

The returned `image_url` is downloaded and stored server-side when the item is saved; the
client posts it back as `payload.source_image_url` rather than re-uploading bytes.

**SSRF guard**: only `http`/`https`, and the resolved IP must be public — private, loopback,
and link-local ranges are rejected with **400**.

### `GET /api/items/brands`

**200** `[{ "name": "Fiskars", "item_count": 2 }]`, commonest first. Feeds the brand field's
autocomplete. A brand is stored with whichever spelling most items already use, so `ikea`
saved against an inventory holding `Ikea` is stored as `Ikea`.

### `GET /api/items/similar?name=…`

**200** `[ItemSummary]`, at most 5. Items whose names share a distinctive word with `name`,
compared with accents stripped — `Poang armchair` finds `POÄNG`, which a SQL `LIKE` cannot.
Common words (`chair`, `table`, `set`) do not count, and brand is not part of the comparison:
owning two IKEA things is normal. A warning for the client to show, never a block.

## Rooms and categories

### `GET /api/rooms`, `GET /api/categories`

**200** `[{ "id": "…", "name": "Kitchen", "item_count": 12, "parent_id": null }]`

Categories nest one level: `parent_id` names the category a shelf sits under, and is always
`null` for rooms. A parent's `item_count` includes its children's, because selecting a parent
filters to its children's items too.

### `POST /api/rooms`, `POST /api/categories`

`{ "name": "Garage" }` → **201**. Duplicate name → **409**. Categories also accept
`parent_id`; a parent that does not exist, or that is itself a shelf, → **400**. One level
only.

### `PATCH /api/rooms/{id}`, `PATCH /api/categories/{id}`

`{ "name": "…" }` → **200**.

### `DELETE /api/rooms/{id}`, `DELETE /api/categories/{id}`

**204** when unused; **409** `{"detail": "3 items are still in this room"}` when in use
(FR-015). A category that still has shelves inside it → **409**.

## Boards

### `GET /api/boards`

**200** `[{ "id": "…", "name": "Autumn wedding outfit", "item_count": 6, "cover_thumb_url": "…" }]`

### `POST /api/boards`

`{ "name": "Lounge redesign" }` → **201**.

### `GET /api/boards/{id}`

```json
// 200
{
  "id": "…", "name": "Lounge redesign",
  "placements": [
    { "id": "…", "item": { "id": "…", "name": "…", "thumb_url": "…" },
      "position_x": 120.5, "position_y": 340.0, "scale": 1.4, "z_index": 2 }
  ]
}
```

### `PUT /api/boards/{id}/placements`

Replaces the whole placement set in one transaction — the canvas saves as a unit, so partial
board states are impossible (FR-018).

```json
// request
{ "placements": [ { "item_id": "…", "position_x": 120.5, "position_y": 340.0, "scale": 1.4, "z_index": 2 } ] }
// 200: the board as returned by GET
```

### `PATCH /api/boards/{id}` · `DELETE /api/boards/{id}`

Rename (**200**) and delete (**204**). Deleting a board never touches the items on it.

## Media

### `GET /api/media/{key}`

Returns the image bytes for a stored object, gated by the session cookie (FR-024), with
`Cache-Control: private, max-age=31536000` since object keys are immutable. This is what
`image_url`, `thumb_url`, and `receipt_url` point at.

## Health

### `GET /api/health`

**200** `{ "status": "ok" }` — unauthenticated, for Cloud Run's startup probe only. Leaks
nothing about the inventory.
