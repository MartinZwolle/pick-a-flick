"""add streaming availability cache

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "movie_availability_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.String(length=4), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=120), nullable=False),
        sa.Column("provider_slug", sa.String(length=80), nullable=False),
        sa.Column("access_type", sa.String(length=20), nullable=False),
        sa.Column("logo_path", sa.String(length=255)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("movie_id", "country", "provider_id", "access_type", name="uq_movie_availability"),
    )
    op.create_index("ix_movie_availability_cache_movie_id", "movie_availability_cache", ["movie_id"])
    op.create_table(
        "movie_availability_fetches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.String(length=4), nullable=False),
        sa.Column("source_link", sa.String(length=500)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("movie_id", "country", name="uq_movie_availability_fetch"),
    )
    op.create_index("ix_movie_availability_fetches_movie_id", "movie_availability_fetches", ["movie_id"])

def downgrade() -> None:
    op.drop_index("ix_movie_availability_fetches_movie_id", table_name="movie_availability_fetches")
    op.drop_table("movie_availability_fetches")
    op.drop_index("ix_movie_availability_cache_movie_id", table_name="movie_availability_cache")
    op.drop_table("movie_availability_cache")
