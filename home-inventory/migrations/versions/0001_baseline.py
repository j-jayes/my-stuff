"""The schema as it stood when Alembic was adopted.

Databases created before this revision existed already have these tables, built by
create_all. They are stamped at this revision rather than being run through it — see
app/db.py.

Revision ID: 0001_baseline
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boards",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=True),
        sa.Column("descriptor_notes", sa.Text(), nullable=True),
        sa.Column("purchase_price_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("purchase_date", sa.String(), nullable=True),
        sa.Column("serial_number", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("image_key", sa.String(), nullable=True),
        sa.Column("thumb_key", sa.String(), nullable=True),
        sa.Column("receipt_key", sa.String(), nullable=True),
        sa.Column("room_id", sa.String(), nullable=True),
        sa.Column("category_id", sa.String(), nullable=True),
        sa.Column("ai_suggested_fields", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("purchase_price_minor IS NULL OR purchase_price_minor >= 0"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_category_id", "items", ["category_id"])
    op.create_index("ix_items_created_at", "items", ["created_at"])
    op.create_index("ix_items_room_id", "items", ["room_id"])
    op.create_table(
        "board_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("board_id", sa.String(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("position_x", sa.Float(), nullable=False),
        sa.Column("position_y", sa.Float(), nullable=False),
        sa.Column("scale", sa.Float(), nullable=False),
        sa.Column("z_index", sa.Integer(), nullable=False),
        sa.CheckConstraint("scale > 0"),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("board_id", "item_id"),
    )


def downgrade() -> None:
    op.drop_table("board_items")
    op.drop_index("ix_items_room_id", "items")
    op.drop_index("ix_items_created_at", "items")
    op.drop_index("ix_items_category_id", "items")
    op.drop_table("items")
    op.drop_table("rooms")
    op.drop_table("categories")
    op.drop_table("boards")
