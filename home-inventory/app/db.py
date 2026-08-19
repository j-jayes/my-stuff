"""Database wiring, and the write path that keeps the snapshot in storage up to date."""

import threading
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import SEED_CATEGORIES, SEED_ROOMS, Base, Category, Room
from app.snapshot import DatabaseSnapshot, GcsObjectStore

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_snapshot: DatabaseSnapshot | None = None
# max-instances=1 means one process, but uvicorn still serves requests concurrently. Serialise
# the snapshot upload so two saves cannot interleave and race the generation number.
_snapshot_lock = threading.Lock()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    """SQLite ignores foreign keys unless asked, which would silently defeat the ON DELETE
    RESTRICT that stops an in-use room being deleted."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init(settings: Settings) -> None:
    global _engine, _session_factory, _snapshot

    path = Path(settings.db_path)
    store = (
        GcsObjectStore(settings.db_bucket, project=settings.gcp_project)
        if settings.db_bucket
        else None
    )
    _snapshot = DatabaseSnapshot(store, settings.db_object, path)
    _snapshot.restore()

    path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}, future=True
    )
    Base.metadata.create_all(_engine)
    _session_factory = sessionmaker(_engine, expire_on_commit=False)

    with _session_factory() as session:
        _seed(session)
        session.commit()

    # A brand new database is not in storage yet; put it there so a restart finds it.
    if _snapshot.enabled and _snapshot.generation is None:
        save_snapshot()


def _seed(session: Session) -> None:
    if session.scalar(select(Room).limit(1)) is None:
        session.add_all(Room(name=n, sort_order=i) for i, n in enumerate(SEED_ROOMS))
    if session.scalar(select(Category).limit(1)) is None:
        session.add_all(Category(name=n, sort_order=i) for i, n in enumerate(SEED_CATEGORIES))


def get_session() -> Iterator[Session]:
    assert _session_factory is not None, "db.init() has not been called"
    with _session_factory() as session:
        yield session


def save_snapshot() -> None:
    """Push the database to object storage. Call after every committed write.

    Raises StaleSnapshotError if another instance wrote first, which the API turns into a 409.
    """
    assert _snapshot is not None, "db.init() has not been called"
    if not _snapshot.enabled:
        return
    with _snapshot_lock:
        # WAL pages have to be folded back into the main file before it is worth copying.
        assert _engine is not None
        with _engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        _snapshot.save()


def reset_for_tests() -> None:
    global _engine, _session_factory, _snapshot
    if _engine is not None:
        _engine.dispose()
    _engine = _session_factory = _snapshot = None
