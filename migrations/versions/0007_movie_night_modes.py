"""movie night discovery modes
Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision="0007"
down_revision="0006"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("movie_nights",sa.Column("mode",sa.String(30),nullable=False,server_default="normal"))
    op.add_column("movie_nights",sa.Column("relaxation_note",sa.String(240),nullable=True))

def downgrade():
    op.drop_column("movie_nights","relaxation_note")
    op.drop_column("movie_nights","mode")
