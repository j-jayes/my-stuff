"""A second level of category, so "Kitchenware" stops meaning everything in the kitchen.

Only the column is added here. The twelve shelves under Kitchenware are seed data, topped
up by name in app/db.py, because the owner is free to rename or delete them afterwards.

Revision ID: 0003_category_parent
Revises: 0002_item_quantity
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_category_parent"
down_revision = "0002_item_quantity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch mode: SQLite cannot attach a foreign key to a live table, so Alembic rebuilds it.
    with op.batch_alter_table("categories") as batch:
        batch.add_column(sa.Column("parent_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_categories_parent_id", "categories", ["parent_id"], ["id"], ondelete="RESTRICT"
        )


def downgrade() -> None:
    with op.batch_alter_table("categories") as batch:
        batch.drop_constraint("fk_categories_parent_id", type_="foreignkey")
        batch.drop_column("parent_id")
