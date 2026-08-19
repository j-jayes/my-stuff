"""Alembic environment.

Two ways in. The app calls command.upgrade() with a live connection in
config.attributes["connection"], so the migration runs on the same engine the app already
opened. The alembic CLI has no such connection and falls back to Settings.db_path.
"""

from alembic import context
from sqlalchemy import create_engine

from app.config import Settings
from app.models import Base

target_metadata = Base.metadata


def _url() -> str:
    return f"sqlite:///{Settings().db_path}"


def _configure(connection) -> None:
    # render_as_batch: SQLite cannot ALTER a constraint in place, so Alembic recreates the
    # table instead. Without this, adding a foreign key silently produces nothing.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _configure(connection)
        context.run_migrations()
        return

    engine = create_engine(_url())
    try:
        with engine.connect() as own_connection:
            _configure(own_connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
