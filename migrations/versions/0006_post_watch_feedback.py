"""post-watch feedback
Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision="0006"
down_revision="0005"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table(
        "watch_events",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("movie_night_id",sa.Integer(),sa.ForeignKey("movie_nights.id",ondelete="SET NULL")),
        sa.Column("movie_id",sa.Integer(),sa.ForeignKey("movies.id",ondelete="CASCADE"),nullable=False),
        sa.Column("status",sa.String(20),nullable=False,server_default="watched"),
        sa.Column("watched_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.UniqueConstraint("movie_night_id",name="uq_watch_event_movie_night"),
    )
    op.create_table(
        "watch_participants",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("watch_event_id",sa.Integer(),sa.ForeignKey("watch_events.id",ondelete="CASCADE"),nullable=False),
        sa.Column("profile_id",sa.Integer(),sa.ForeignKey("profiles.id",ondelete="CASCADE"),nullable=False),
        sa.Column("rating",sa.Integer()),
        sa.Column("rewatchable",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("abandoned",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.UniqueConstraint("watch_event_id","profile_id",name="uq_watch_participant"),
    )

def downgrade():
    op.drop_table("watch_participants")
    op.drop_table("watch_events")
