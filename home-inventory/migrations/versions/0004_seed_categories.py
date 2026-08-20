"""Add the seed categories an existing database never got.

Seeding in application code only fires on an empty table, so every category added to the seed
list after the first boot was invisible to any database that already existed — which is all of
them. Doing it here instead means it happens exactly once: a category deleted afterwards stays
deleted, which a top-up on every boot could not promise.

Sort order is rewritten for the seeded names so that a database migrated to here and one
created fresh list their categories in the same order.

Revision ID: 0004_seed_categories
Revises: 0003_category_parent
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.models import SEED_CATEGORIES, SEED_SUBCATEGORIES

revision = "0004_seed_categories"
down_revision = "0003_category_parent"
branch_labels = None
depends_on = None

categories = sa.table(
    "categories",
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("sort_order", sa.Integer),
    sa.column("parent_id", sa.String),
    sa.column("created_at", sa.String),
)


def upgrade() -> None:
    connection = op.get_bind()
    existing = {
        name: id_ for id_, name in connection.execute(sa.select(categories.c.id, categories.c.name))
    }
    # A database with no categories at all is brand new; application seeding will fill it.
    if not existing:
        return

    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = []

    for order, name in enumerate(SEED_CATEGORIES):
        if name in existing:
            connection.execute(
                categories.update().where(categories.c.name == name).values(sort_order=order)
            )
        else:
            new_id = str(uuid.uuid4())
            existing[name] = new_id
            rows.append(
                {
                    "id": new_id,
                    "name": name,
                    "sort_order": order,
                    "parent_id": None,
                    "created_at": now,
                }
            )

    if rows:
        op.bulk_insert(categories, rows)
        rows = []

    for parent_name, shelves in SEED_SUBCATEGORIES.items():
        parent_id = existing.get(parent_name)
        if parent_id is None:
            continue  # the owner deleted or renamed it; do not put it back
        for order, name in enumerate(shelves):
            if name in existing:
                continue
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "sort_order": order,
                    "parent_id": parent_id,
                    "created_at": now,
                }
            )

    if rows:
        op.bulk_insert(categories, rows)


def downgrade() -> None:
    """Deliberately not reversible: which of these the owner has since filed items under is
    not knowable here, and dropping a category with items would fail anyway."""
    pass
