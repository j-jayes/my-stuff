"""Where the owner's own photograph goes when a generated one takes its place.

A product photo made from a photograph is a derivative of it. The photograph is the evidence
that this particular thing is owned — and what it actually looks like, wear and all — so
accepting a generated image moves the original aside rather than dropping it.

The key has to be a column rather than a convention: storage can put, open and delete, but it
cannot list, so an object no row names could never be found again to clean up.

Revision ID: 0007_item_source_image
Revises: 0006_seed_closet_and_clothing
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_item_source_image"
down_revision = "0006_seed_closet_and_clothing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("items") as batch:
        batch.add_column(sa.Column("source_image_key", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("items") as batch:
        batch.drop_column("source_image_key")
