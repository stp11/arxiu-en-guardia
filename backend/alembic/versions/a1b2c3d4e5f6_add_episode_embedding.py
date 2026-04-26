"""add episode embedding

Revision ID: a1b2c3d4e5f6
Revises: 163074400914
Create Date: 2026-02-08 20:00:00.000000

"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "163074400914"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "episode",
        sa.Column("embedding", Vector(1536), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("episode", "embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")
