"""Alembic owns the schema. These tests guard the two cases that matter in production: a
brand new database file, and the pre-Alembic database that is already sitting in GCS.

All offline — no bucket, no network.
"""

import sqlalchemy as sa

from app import db
from app.models import Base


def _tables(path: str) -> dict[str, set[str]]:
    engine = sa.create_engine(f"sqlite:///{path}")
    try:
        inspector = sa.inspect(engine)
        return {
            name: {c["name"] for c in inspector.get_columns(name)}
            for name in inspector.get_table_names()
        }
    finally:
        engine.dispose()


def test_a_new_database_is_built_to_match_the_orm(settings):
    """Nothing calls create_all any more, so the migrations must produce the same schema the
    models declare — otherwise a fresh dev database and production drift apart."""
    db.reset_for_tests()
    db.init(settings)
    db.reset_for_tests()

    built = _tables(settings.db_path)
    for table in Base.metadata.sorted_tables:
        assert table.name in built, f"{table.name} was never created"
        declared = {column.name for column in table.columns}
        assert declared <= built[table.name], (
            f"{table.name} is missing {declared - built[table.name]}"
        )
    assert "alembic_version" in built


def test_a_pre_alembic_database_is_adopted_rather_than_rebuilt(settings):
    """The deployed file was created by create_all and has no alembic_version table. It must
    be stamped at the baseline and carried forward, with its rows intact."""
    engine = sa.create_engine(f"sqlite:///{settings.db_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO items (id, name, created_at, updated_at)"
                " VALUES ('keep-me', 'Steam iron', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
    engine.dispose()

    db.reset_for_tests()
    db.init(settings)
    db.reset_for_tests()

    built = _tables(settings.db_path)
    assert "alembic_version" in built

    engine = sa.create_engine(f"sqlite:///{settings.db_path}")
    with engine.connect() as connection:
        assert (
            connection.execute(sa.text("SELECT name FROM items WHERE id='keep-me'")).scalar()
            == "Steam iron"
        )
        version = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    assert version == db.head_revision()


def test_initialising_twice_is_a_no_op(settings):
    db.reset_for_tests()
    db.init(settings)
    db.reset_for_tests()
    db.init(settings)
    db.reset_for_tests()

    engine = sa.create_engine(f"sqlite:///{settings.db_path}")
    with engine.connect() as connection:
        # Seeding is guarded on emptiness, so a second init must not double the categories.
        assert connection.execute(sa.text("SELECT count(*) FROM categories")).scalar() == 9
    engine.dispose()
