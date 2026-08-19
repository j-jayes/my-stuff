"""Alembic owns the schema. These tests guard the two cases that matter in production: a
brand new database file, and the pre-Alembic database that is already sitting in GCS.

All offline — no bucket, no network.
"""

import sqlalchemy as sa
from alembic import command

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
    be stamped at the baseline, carried forward to head, and keep its rows.

    The old shape is built by migrating to the baseline and then dropping the version table,
    rather than by create_all on today's metadata — create_all would build today's columns,
    which is precisely what the deployed file does not have.
    """
    config = db._alembic_config()
    engine = sa.create_engine(f"sqlite:///{settings.db_path}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, db.BASELINE_REVISION)
        connection.execute(sa.text("DROP TABLE alembic_version"))
    with engine.begin() as connection:
        assert "quantity" not in {c["name"] for c in sa.inspect(connection).get_columns("items")}
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
        row = connection.execute(
            sa.text("SELECT name, quantity FROM items WHERE id='keep-me'")
        ).one()
        # The row survives, and a column added after it was written gets the default.
        assert row.name == "Steam iron"
        assert row.quantity == 1
        version = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    assert version == db.head_revision()


def _category_names(path: str) -> list[str]:
    engine = sa.create_engine(f"sqlite:///{path}")
    try:
        with engine.connect() as connection:
            return sorted(connection.scalars(sa.text("SELECT name FROM categories")))
    finally:
        engine.dispose()


def test_initialising_twice_is_a_no_op(settings):
    """The subcategories are topped up by name on every boot rather than seeded once, so a
    restart is the case most likely to duplicate them."""
    db.reset_for_tests()
    db.init(settings)
    db.reset_for_tests()
    after_first = _category_names(settings.db_path)

    db.init(settings)
    db.reset_for_tests()

    assert _category_names(settings.db_path) == after_first
    assert len(after_first) == len(set(after_first))


def test_a_database_with_items_in_it_still_migrates(settings):
    """SQLite rebuilds a table to alter it, and a rebuild of categories breaks every item
    pointing at one while foreign keys are enforced. An empty database never hits this, so
    this test has to put a real row in the way first.
    """
    config = db._alembic_config()
    engine = sa.create_engine(f"sqlite:///{settings.db_path}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, db.BASELINE_REVISION)
        connection.execute(
            sa.text(
                "INSERT INTO categories (id, name, sort_order, created_at)"
                " VALUES ('cat-1', 'Kitchenware', 0, '2026-01-01T00:00:00Z')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO items (id, name, category_id, created_at, updated_at)"
                " VALUES ('itm-1', 'Bread knife', 'cat-1',"
                " '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
    engine.dispose()

    db.reset_for_tests()
    db.init(settings)
    db.reset_for_tests()

    engine = sa.create_engine(f"sqlite:///{settings.db_path}")
    with engine.connect() as connection:
        # The item still points at the category it pointed at, and nothing dangles.
        assert (
            connection.execute(sa.text("SELECT category_id FROM items WHERE id='itm-1'")).scalar()
            == "cat-1"
        )
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    engine.dispose()
