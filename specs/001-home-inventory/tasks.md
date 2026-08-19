# Tasks: Home Inventory

Status as of 2026-08-19. Phases 1–7 are done, deployed, and verified against the live service.

## Phase 1 — Infrastructure ✅

- [x] GCP project `my-stuff-inventory`, billed to the Cabri account (the two other open accounts
      were at their project quota)
- [x] APIs enabled: Run, Cloud Build, Artifact Registry, Storage, Vertex AI, Secret Manager
- [x] Buckets `my-stuff-inventory-media` and `my-stuff-inventory-db` in `europe-north1`
- [x] Service account `inventory-app@` with objectAdmin on both buckets, `aiplatform.user`,
      and secret accessor
- [x] Secrets `inventory-app-password` and `inventory-session-key`

## Phase 2 — Backend foundation ✅

- [x] `uv` project with `.venv`, `pyproject.toml`, `uv.lock`
- [x] SQLAlchemy models for Item, Room, Category, Board, BoardItem
- [x] Seeded rooms and categories
- [x] `DatabaseSnapshot`: restore on boot, save after each write, generation precondition
- [x] Tests for the stale-writer rejection **written first and seen failing**

## Phase 3 — Auth ✅

- [x] Password check, signed session cookie, `require_session` dependency
- [x] Test asserting all 14 data routes return 401 without a session

## Phase 4 — Items, storage, imaging ✅

- [x] Items CRUD, filters, search, taxonomy management with in-use protection
- [x] `LocalMediaStorage` / `GcsMediaStorage` behind one interface
- [x] Thumbnails via Pillow with `exif_transpose`; `pillow-heif` registered
- [x] Media served through the app behind the session cookie

## Phase 5 — Capture helpers ✅

- [x] `/api/items/extract` against Gemini 3.1 Flash-Lite with a dynamic category enum
- [x] `/api/items/scrape` with og:image/twitter:card fallback and an SSRF guard
- [x] SSRF tests written first; verified live that the metadata server is refused

## Phase 6 — Frontend ✅

- [x] Vite + React SPA, mobile-first, built into `app/static`
- [x] Login, inventory list with search and filters, item detail and edit
- [x] Magic Add: camera capture → suggestions → editable form, with suggestion badges
- [x] Link-first add with server-side image fetch
- [x] Gallery and the board canvas (pointer events, 1000×1000 canvas units)

## Phase 7 — Container and deployment ✅

- [x] Multi-stage Dockerfile; `docker-compose.yml` running the same image
- [x] `scripts/deploy.sh`
- [x] Deployed to `https://my-stuff-716260291301.europe-north1.run.app`
- [x] **Cold-start test passed**: a new revision restored the database from GCS intact
- [x] Confirmed `minScale=0`, `maxScale=1`, request-based billing

## Phase 8 — Visual redesign and desktop layout ✅

- [x] Design tokens in `frontend/src/styles/tokens.css`: blog colours and type, Drake's spatial
      language (cream ground, squared corners, hairline rules)
- [x] Five self-hosted woff2 faces, 104 KB — Noto Serif JP 300, Lato 400/700, IBM Plex Mono
- [x] Two-blue palette forced by contrast: `#2b8cbe` for headings, `#1a6d94` for interactive
- [x] `scripts/check_contrast.py` asserting 24 pairs across light and dark palettes
- [x] Desktop sidebar with room and category filters; filters moved into the URL
- [x] Drake's-style product grid, two-column item page, board canvas with a side rail
- [x] Verified at 390 / 834 / 1440 px, light and dark, no horizontal scroll, one nav per viewport

## Remaining

- [ ] Exercise the capture flow on Jonathan's actual iPhone — the one thing that cannot be
      verified from here, and where the EXIF-rotation and HEIC handling really get tested
- [ ] Alembic migrations. The schema is currently created by `create_all`, which is fine until
      the first schema change; add migrations before altering any table
- [ ] Frontend component tests (Vitest). Currently the frontend is covered only by the manual
      and Playwright passes
- [ ] Board canvas pinch-to-zoom on touch; today scaling is a slider
- [ ] A "recently added" default sort toggle, if the list ever feels unwieldy
