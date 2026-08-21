"""Whether the thing was bought used.

Nothing recorded so far was known to be second hand, so existing rows take the default.

Revision ID: 0005_item_second_hand
Revises: 0004_seed_categories
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_item_second_hand"
down_revision = "0004_seed_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills the existing rows; the ORM default takes over for new ones.
    with op.batch_alter_table("items") as batch:
        batch.add_column(sa.Column("second_hand", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("items") as batch:
        batch.drop_column("second_hand")
