"""add wikipedia articles

Revision ID: 04ce7fdd6060
Revises: a1b2c3d4e5f6
Create Date: 2026-10-20 17:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision = "04ce7fdd6060"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wikipediaarticle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_wikipediaarticle_title"),
        "wikipediaarticle",
        ["title"],
        unique=True,
    )
    op.create_table(
        "episodewikipediaarticle",
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"]),
        sa.ForeignKeyConstraint(["article_id"], ["wikipediaarticle.id"]),
        sa.PrimaryKeyConstraint("episode_id", "article_id"),
    )
    op.add_column(
        "episode",
        sa.Column("wikipedia_checked_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("episode", "wikipedia_checked_at")
    op.drop_table("episodewikipediaarticle")
    op.drop_index(
        op.f("ix_wikipediaarticle_title"), table_name="wikipediaarticle"
    )
    op.drop_table("wikipediaarticle")
