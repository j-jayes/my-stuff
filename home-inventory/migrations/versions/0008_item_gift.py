"""Mark an item as given away, and to whom, without losing the record of it.

gifted_at is what says an item has left the house. The recipient is separate because it is
optional: some gifts are not worth naming.

Revision ID: 0008_item_gift
Revises: 0007_item_source_image
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_item_gift"
down_revision = "0007_item_source_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("items") as batch:
        batch.add_column(sa.Column("gifted_at", sa.String(), nullable=True))
        batch.add_column(sa.Column("gifted_to", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("items") as batch:
        batch.drop_column("gifted_to")
        batch.drop_column("gifted_at")
