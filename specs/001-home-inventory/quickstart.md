# Quickstart: Home Inventory

## Prerequisites

- `uv` (Python toolchain), Node 22+, Docker Desktop, `gcloud` authenticated.
- Application Default Credentials for the Gemini calls:
  `gcloud auth application-default login`

## First-time setup

```bash
cd home-inventory
cp .env.example .env          # then fill in APP_PASSWORD and SESSION_SECRET
uv venv                       # creates home-inventory/.venv
uv sync                       # installs backend deps into .venv
(cd frontend && npm install)
```

## Day-to-day development

Two loops, pick the one that fits what you are doing.

### Fast loop — hot reload (what you use 95% of the time)

```bash
# terminal 1
uv run uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev        # http://localhost:5173, proxies /api to :8000
```

SQLite lives at `home-inventory/dev.sqlite` (gitignored). Images go to a local
`home-inventory/dev-media/` directory instead of GCS — the storage layer picks its backend from
`STORAGE_BACKEND=local|gcs`, so no cloud access is needed to work on the UI.

### Production-parity loop — Docker Compose

```bash
docker compose up --build          # http://localhost:8080
```

This builds the **same Dockerfile that Cloud Run runs**, so it catches the class of bug the
fast loop cannot: missing system packages, a frontend that was never built into the image, a
broken entrypoint. Run it before every deploy. `STORAGE_BACKEND=gcs` here, mounting your ADC
credentials read-only, exercises the real GCS path locally.

## Tests

```bash
uv run pytest                      # backend, fast, no cloud access needed
cd frontend && npm test            # component tests
uv run pytest -m integration       # hits real GCS + Vertex; needs ADC
```

## Deploy

```bash
./scripts/deploy.sh                # gcloud run deploy --source, one command
```

## Verifying it actually works

After deploying, do this by hand — passing tests are not evidence:

1. Open the Cloud Run URL on your **phone**, sign in with the app password.
2. Photograph something; confirm the form arrives pre-filled and saving works.
3. Paste a product URL; confirm the image is fetched.
4. Check the object landed: `gcloud storage ls gs://my-stuff-inventory-media/items/`
5. Force a cold start (`gcloud run services update … --no-traffic` then restore, or just wait),
   reload, and confirm your items are still there — this is the test that proves the database
   replication and restore path works, and it is the one most likely to fail.
