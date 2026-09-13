"""movie night flow
Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
revision="0005";down_revision="0004";branch_labels=None;depends_on=None
def upgrade():
 op.create_table("movie_nights",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("status",sa.String(20),nullable=False,server_default="choosing"),sa.Column("moods",sa.String(120)),sa.Column("runtime_max",sa.Integer()),sa.Column("selected_movie_id",sa.Integer(),sa.ForeignKey("movies.id",ondelete="SET NULL")),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
 op.create_table("movie_night_viewers",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("movie_night_id",sa.Integer(),sa.ForeignKey("movie_nights.id",ondelete="CASCADE"),nullable=False),sa.Column("profile_id",sa.Integer(),sa.ForeignKey("profiles.id",ondelete="CASCADE"),nullable=False),sa.UniqueConstraint("movie_night_id","profile_id",name="uq_movie_night_viewer"))
 op.create_table("movie_night_candidates",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("movie_night_id",sa.Integer(),sa.ForeignKey("movie_nights.id",ondelete="CASCADE"),nullable=False),sa.Column("movie_id",sa.Integer(),sa.ForeignKey("movies.id",ondelete="CASCADE"),nullable=False),sa.Column("score",sa.Float(),nullable=False,server_default="0"),sa.Column("reasons_json",sa.Text(),nullable=False,server_default="[]"),sa.Column("decision",sa.String(30)),sa.UniqueConstraint("movie_night_id","movie_id",name="uq_movie_night_candidate"))
 op.create_table("group_movie_vetoes",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("viewer_key",sa.String(200),nullable=False),sa.Column("movie_id",sa.Integer(),sa.ForeignKey("movies.id",ondelete="CASCADE"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.UniqueConstraint("viewer_key","movie_id",name="uq_group_movie_veto"))
 op.create_index("ix_group_movie_vetoes_viewer_key","group_movie_vetoes",["viewer_key"])
def downgrade():
 op.drop_index("ix_group_movie_vetoes_viewer_key",table_name="group_movie_vetoes");op.drop_table("group_movie_vetoes");op.drop_table("movie_night_candidates");op.drop_table("movie_night_viewers");op.drop_table("movie_nights")
