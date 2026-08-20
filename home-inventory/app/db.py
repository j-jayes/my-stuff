"""Database wiring, and the write path that keeps the snapshot in storage up to date."""

import threading
from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import SEED_CATEGORIES, SEED_ROOMS, SEED_SUBCATEGORIES, Category, Room
from app.snapshot import DatabaseSnapshot, GcsObjectStore

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
# The revision that describes the schema as it was when Alembic was adopted. A database from
# before then already looks like this, so it is stamped here rather than migrated to here.
BASELINE_REVISION = "0001_baseline"

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_snapshot: DatabaseSnapshot | None = None
# max-instances=1 means one process, but uvicorn still serves requests concurrently. Serialise
# the snapshot upload so two saves cannot interleave and race the generation number.
_snapshot_lock = threading.Lock()


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    # script_location in the ini is resolved against the working directory, not against the
    # ini. Pin it, or the app only boots when it happens to be started from this directory.
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    return config


def head_revision() -> str:
    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


def _upgrade_schema(engine: Engine) -> bool:
    """Bring the schema to head, and return whether that changed anything.

    Alembic owns the schema, including on a brand new file — create_all is not called
    anywhere any more. The awkward case is the database already in storage: it was built by
    create_all and has every table but no alembic_version, so running the baseline against it
    would fail on "table already exists". Stamp it instead.
    """
    config = _alembic_config()
    with engine.connect() as connection:
        # SQLite cannot alter a table in place, so Alembic rebuilds it: rename, recreate,
        # copy, drop. With foreign keys enforced — which _enable_sqlite_foreign_keys does on
        # every connection — that drop breaks every row pointing at the table being rebuilt.
        # It only bites a database that already holds data, so an empty test database would
        # never show it. Enforcement goes back on below, and the result is checked.
        # Driven through the raw DBAPI connection on purpose: SQLite treats this pragma as a
        # no-op inside a transaction, and going through SQLAlchemy would autobegin one.
        raw = connection.connection.dbapi_connection
        raw.execute("PRAGMA foreign_keys=OFF")
        assert raw.execute("PRAGMA foreign_keys").fetchone()[0] == 0, "pragma did not take"

        config.attributes["connection"] = connection
        with connection.begin():
            tables = set(inspect(connection).get_table_names())
            if "items" in tables and "alembic_version" not in tables:
                command.stamp(config, BASELINE_REVISION)
            before = MigrationContext.configure(connection).get_current_revision()
            command.upgrade(config, "head")

        raw.execute("PRAGMA foreign_keys=ON")
        dangling = raw.execute("PRAGMA foreign_key_check").fetchall()
        if dangling:
            raise RuntimeError(f"Migration left dangling references: {dangling[:5]}")
        return before != head_revision()


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
    migrated = _upgrade_schema(_engine)
    _session_factory = sessionmaker(_engine, expire_on_commit=False)

    with _session_factory() as session:
        _seed(session)
        session.commit()

    # A brand new database is not in storage yet; put it there so a restart finds it. A
    # migrated one must go back too, or the copy in storage keeps its old shape and every
    # cold start migrates a file that is never written back.
    if _snapshot.enabled and (_snapshot.generation is None or migrated):
        save_snapshot()


def _seed(session: Session) -> None:
    if session.scalar(select(Room).limit(1)) is None:
        session.add_all(Room(name=n, sort_order=i) for i, n in enumerate(SEED_ROOMS))
    if session.scalar(select(Category).limit(1)) is None:
        _seed_categories(session)


def _seed_categories(session: Session) -> None:
    """Fill a brand new database with the whole category tree.

    Only ever called on an empty table. An existing database is topped up by migration
    0004 instead, so that a category deleted afterwards is not resurrected on the next boot.
    """
    parents = {
        name: Category(name=name, sort_order=order) for order, name in enumerate(SEED_CATEGORIES)
    }
    session.add_all(parents.values())
    session.flush()
    session.add_all(
        Category(name=name, parent_id=parents[parent_name].id, sort_order=order)
        for parent_name, shelves in SEED_SUBCATEGORIES.items()
        for order, name in enumerate(shelves)
    )


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
