"""How many of a thing the item is: six glasses are one row, not six.

Existing rows are all single objects, so they take the default.

Revision ID: 0002_item_quantity
Revises: 0001_baseline
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_item_quantity"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills the existing rows; the ORM default takes over for new ones.
    # batch mode so the CHECK lands — SQLite cannot add a constraint to a live table.
    with op.batch_alter_table("items") as batch:
        batch.add_column(sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_items_quantity_positive", "quantity >= 1")


def downgrade() -> None:
    with op.batch_alter_table("items") as batch:
        batch.drop_constraint("ck_items_quantity_positive", type_="check")
        batch.drop_column("quantity")
