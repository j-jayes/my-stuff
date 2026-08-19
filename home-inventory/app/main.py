import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db, deps
from app.config import get_settings
from app.routers import auth, boards, items, media, taxonomy
from app.snapshot import StaleSnapshotError

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    db.init(settings)
    deps.init_storage(settings)
    yield


app = FastAPI(title="My Stuff", lifespan=lifespan)


@app.exception_handler(StaleSnapshotError)
async def stale_snapshot_handler(_: Request, exc: StaleSnapshotError) -> JSONResponse:
    """Another instance wrote first. The owner's change is not saved, and saying so is the only
    honest response — silently retrying could overwrite whatever the other instance wrote."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Something else changed the inventory first. Reload and try again."},
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(items.router)
app.include_router(taxonomy.rooms_router)
app.include_router(taxonomy.categories_router)
app.include_router(boards.router)
app.include_router(media.router)


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        """Serve the built frontend, letting the client router own every non-API path."""
        candidate = STATIC_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
