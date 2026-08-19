# Implementation Plan: Home Inventory ("My Stuff")

**Branch**: `001-home-inventory` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-home-inventory/spec.md`

## Summary

A single-user, mobile-first web app for cataloguing household possessions. One FastAPI service
serves both a React SPA and a JSON API, runs on Cloud Run scaling to zero, keeps its data in a
SQLite file that the app itself snapshots to Cloud Storage after every write, keeps photos in a
private GCS bucket, and uses Gemini 3.1 Flash-Lite to pre-fill the item form from a photo.

The design target is **$0/month at rest**. Every architectural choice in
[research.md](./research.md) was made against that constraint, and one of them — dropping
Litestream — reversed the original brief because Litestream would have forced an always-on
instance costing $25–50/month.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 / React 19 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, `google-genai` 2.18,
`google-cloud-storage`, Pillow + `pillow-heif`, `httpx`, `selectolax` or BeautifulSoup4,
`itsdangerous`; Vite, React Router, TanStack Query, `@dnd-kit` for the board canvas

**Storage**: SQLite (single file, snapshotted to GCS); Google Cloud Storage for images

**Testing**: pytest + `httpx.ASGITransport` for the API, Vitest + Testing Library for
components, Playwright at a mobile viewport for the capture flow

**Target Platform**: Cloud Run (`europe-north1`), consumed from mobile Safari and desktop
browsers

**Project Type**: Web application — one deployable, backend serves the built frontend

**Performance Goals**: suggestions within 5s p90 (measured: 2.65s); list view usable within 3s
at 500 items; save round-trip under 2s

**Constraints**: ~$0/month at rest; Gemini 3.x only available at `location="global"`; Cloud Run
filesystem is tmpfs, so the database lives in memory and must stay small (measured: 496 KiB at
2,000 items)

**Scale/Scope**: one user, hundreds to low thousands of items, ~25 API endpoints, ~8 screens

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1 design.*

| Principle | How this design satisfies it |
|---|---|
| I. Single user, no ceremony | No users table, no roles. One password → one signed cookie. |
| II. Frictionless on a phone | Capture path is camera → pre-filled form → save. Native `<input capture>` rather than a custom camera. Thumbnails on every list so mobile data stays small. |
| III. AI suggests, user decides | `/api/items/extract` creates nothing; it returns suggestions into an editable form. Extraction failure returns 502/504 and the client falls back to a blank form — a designed path, not an error. |
| IV. Test-first for logic | Scrapers, the snapshot/precondition logic, validation, and board coordinate persistence get failing tests first. UI is verified by hand and by Playwright against a running instance. |
| V. Minimum code | No repository layer over SQLAlchemy, no service layer over the routers, no custom camera, no background workers, no queue. |
| Cost constraints | Scale-to-zero, `max-instances=1`, no always-on instance, no managed database. Litestream rejected explicitly on cost — see research D3. |
| Single writer | `max-instances=1` plus GCS generation preconditions, which reject a stale writer (tested). |
| Secrets | Secret Manager only; already created and unreadable from the repo. |
| Reproducible local env | `.venv` via `uv` for the fast loop; `docker compose` running the production Dockerfile for parity. Both mandated by the constitution and both delivered. |

**No violations.** The Complexity Tracking table is therefore omitted.

## Project Structure

### Documentation (this feature)

```text
specs/001-home-inventory/
├── plan.md              # this file
├── spec.md              # what and why
├── research.md          # Phase 0 decisions, with evidence
├── data-model.md        # schema
├── quickstart.md        # how to run it
├── contracts/api.md     # endpoint contract
├── checklists/          # spec quality checklist
└── tasks.md             # produced by /speckit-tasks
```

### Source code (repository root)

```text
home-inventory/
├── pyproject.toml            # uv-managed; creates home-inventory/.venv
├── Dockerfile                # multi-stage: build frontend, then the Python image
├── docker-compose.yml        # runs the SAME Dockerfile locally on :8080
├── .env.example
├── alembic.ini
├── migrations/
├── app/
│   ├── main.py               # FastAPI app, static mount, startup restore
│   ├── config.py             # pydantic-settings; env-driven
│   ├── db.py                 # engine, session, restore-on-boot, snapshot-on-write
│   ├── models.py             # SQLAlchemy models (data-model.md)
│   ├── schemas.py            # Pydantic request/response models
│   ├── auth.py               # password check, signed cookie, dependency
│   ├── storage.py            # LocalStorage | GcsStorage behind one interface
│   ├── imaging.py            # thumbnails, HEIC decode
│   ├── extract.py            # Gemini call, ItemSuggestion schema
│   ├── scrape.py             # og:image fetch + SSRF guard
│   └── routers/
│       ├── auth.py  items.py  taxonomy.py  boards.py  media.py
├── tests/
│   ├── conftest.py           # in-memory app + fake storage
│   ├── test_items.py  test_auth.py  test_scrape.py
│   ├── test_snapshot.py      # the precondition logic
│   └── test_boards.py
└── frontend/
    ├── package.json  vite.config.ts
    └── src/
        ├── main.tsx  App.tsx  api.ts
        ├── pages/    Login  Inventory  ItemDetail  AddItem  Gallery  Boards  BoardCanvas
        └── components/ ItemCard  ItemForm  CameraInput  FilterBar  SuggestionBadge
```

**Structure Decision**: One deployable containing both halves. The frontend is built to static
assets and mounted by FastAPI, so there is a single origin, no CORS layer, no second service,
and one thing to deploy. `home-inventory/` sits alongside the existing `research/` directory
rather than reorganising the repository.

## Implementation sequence

Ordered so that each step is independently verifiable, and so the riskiest unknowns were
retired first (they already were — the Gemini call, HEIC support, and the GCS snapshot are all
proven against the real project in research.md).

1. **Backend skeleton + persistence.** `uv` project, `.venv`, config, models, migrations,
   seeded rooms and categories, restore-on-boot and snapshot-on-write with the generation
   precondition. Verified by `test_snapshot.py` covering the stale-writer rejection.
2. **Auth.** Password check, signed cookie, dependency that guards every router. Verified by a
   test asserting an unauthenticated request to each router returns 401.
3. **Items CRUD + storage + thumbnails.** Local storage backend first so tests need no cloud.
4. **Extract and scrape endpoints.** The Gemini call already has a working reference
   implementation in the research probe; the scraper needs its SSRF guard tested first.
5. **Frontend shell + the capture flow.** Login, inventory list, and the Magic Add path —
   this is the MVP and should be exercised on a real phone as soon as it exists.
6. **Browse, filter, search, item detail and edit.**
7. **Dockerfile + compose, then first deploy.** Deploy before the gallery and boards exist, so
   the deployment path is proven while the app is still small.
8. **Gallery and the board canvas.** Last, because they depend on a populated inventory.

## Verification

The definition of done for this feature, beyond the tests:

- `uv run pytest` and `npm test` pass, and the tests for scraping, snapshotting, and validation
  were each seen failing before their implementation existed.
- `docker compose up --build` serves a working app on `localhost:8080` from the production
  Dockerfile.
- Deployed to Cloud Run, then on an actual phone: sign in, photograph three real objects, and
  confirm the form arrives pre-filled and saving works.
- `gcloud storage ls gs://my-stuff-inventory-media/items/` shows the objects.
- **The cold-start test**: force a new instance, reload, and confirm every item is still there.
  This proves restore-from-GCS works and is the single most likely thing to be silently broken.
- `gcloud run services describe` confirms `min-instances=0` and `max-instances=1` — i.e. that
  the cost design is actually in effect and not just intended.
