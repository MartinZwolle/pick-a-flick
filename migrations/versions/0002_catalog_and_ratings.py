"""create catalog and profile movie ratings

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("original_title", sa.String(length=255)),
        sa.Column("release_year", sa.Integer()),
        sa.Column("release_date", sa.String(length=10)),
        sa.Column("runtime_minutes", sa.Integer()),
        sa.Column("original_language", sa.String(length=12)),
        sa.Column("overview", sa.Text()),
        sa.Column("poster_path", sa.String(length=255)),
        sa.Column("adult", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_source", sa.String(length=40), nullable=False, server_default="tmdb"),
        sa.Column("metadata_fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tmdb_id", name="uq_movies_tmdb_id"),
    )
    op.create_index("ix_movies_tmdb_id", "movies", ["tmdb_id"], unique=True)

    op.create_table(
        "movie_genres",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tmdb_genre_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.UniqueConstraint("movie_id", "tmdb_genre_id", name="uq_movie_genre"),
    )
    op.create_table(
        "movie_credits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tmdb_person_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role_type", sa.String(length=20), nullable=False),
        sa.Column("character", sa.String(length=255)),
        sa.Column("billing_order", sa.Integer()),
    )
    op.create_table(
        "profile_movie_ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seen", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rating", sa.Integer()),
        sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rewatchable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("veto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("profile_id", "movie_id", name="uq_profile_movie_rating"),
    )


def downgrade() -> None:
    op.drop_table("profile_movie_ratings")
    op.drop_table("movie_credits")
    op.drop_table("movie_genres")
    op.drop_index("ix_movies_tmdb_id", table_name="movies")
    op.drop_table("movies")
