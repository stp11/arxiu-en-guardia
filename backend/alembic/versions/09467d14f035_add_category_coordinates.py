"""add category coordinates

Revision ID: 09467d14f035
Revises: 04ce7fdd6060
Create Date: 2026-10-26 18:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "09467d14f035"
down_revision = "04ce7fdd6060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("category", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column(
        "category", sa.Column("longitude", sa.Float(), nullable=True)
    )
    op.add_column(
        "category", sa.Column("geocoded_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("category", "geocoded_at")
    op.drop_column("category", "longitude")
    op.drop_column("category", "latitude")
