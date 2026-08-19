# Stage 1: build the SPA into the location the backend serves from.
FROM mirror.gcr.io/library/node:22-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the runtime image, which is what both Cloud Run and docker compose run.
FROM mirror.gcr.io/library/python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv

WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app/ ./app/
# vite's outDir is ../app/static, which resolves to /app/static in the frontend stage. This
# must land after the app copy, or the app copy would overwrite it.
COPY --from=frontend /app/static ./app/static

# The database lives on the container's writable layer; on Cloud Run that is tmpfs, and it is
# restored from Cloud Storage at startup. See specs/001-home-inventory/research.md D3.
ENV DB_PATH=/srv/data/inventory.sqlite
RUN mkdir -p /srv/data

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
