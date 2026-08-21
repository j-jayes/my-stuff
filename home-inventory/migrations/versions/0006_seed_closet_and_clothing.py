"""A Closet to keep clothes in, and shelves to sort them onto.

Both tables have the same problem 0004 described for categories: application seeding only
fires on an empty table, so anything added to a seed list after first boot never reaches a
database that already exists. Rooms hit it here for the first time — Closet is the first room
added since the original five.

Sort order is rewritten for the seeded room names so a migrated database and a fresh one list
their rooms in the same order.

Revision ID: 0006_seed_closet_and_clothing
Revises: 0005_item_second_hand
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.models import SEED_ROOMS, SEED_SUBCATEGORIES

revision = "0006_seed_closet_and_clothing"
down_revision = "0005_item_second_hand"
branch_labels = None
depends_on = None

CLOTHING = "Clothing & Accessories"

rooms = sa.table(
    "rooms",
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("sort_order", sa.Integer),
    sa.column("created_at", sa.String),
)

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
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    # Each table is judged on its own: a database can be new in one and populated in the other.
    existing_rooms = set(connection.execute(sa.select(rooms.c.name)).scalars())
    if existing_rooms:
        new_rooms = []
        for order, name in enumerate(SEED_ROOMS):
            if name in existing_rooms:
                connection.execute(
                    rooms.update().where(rooms.c.name == name).values(sort_order=order)
                )
            else:
                new_rooms.append(
                    {
                        "id": str(uuid.uuid4()),
                        "name": name,
                        "sort_order": order,
                        "created_at": now,
                    }
                )
        if new_rooms:
            op.bulk_insert(rooms, new_rooms)

    existing_categories = {
        name: id_ for id_, name in connection.execute(sa.select(categories.c.id, categories.c.name))
    }
    if not existing_categories:
        return

    parent_id = existing_categories.get(CLOTHING)
    if parent_id is None:
        return  # the owner deleted or renamed it; do not put it back

    shelves = [
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "sort_order": order,
            "parent_id": parent_id,
            "created_at": now,
        }
        for order, name in enumerate(SEED_SUBCATEGORIES[CLOTHING])
        if name not in existing_categories
    ]
    if shelves:
        op.bulk_insert(categories, shelves)


def downgrade() -> None:
    """Not reversible, for the reason 0004 gives: what the owner has since filed under these
    is not knowable here, and dropping one with items in it would fail anyway."""
    pass
