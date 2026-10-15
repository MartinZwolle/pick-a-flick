"""Single administrator, revocable sessions and web configuration.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.Float(), nullable=False, server_default="0"),
        sa.Column("blocked_until", sa.Float(), nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO admin_state (id) VALUES (1)")
    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("csrf", sa.String(64), nullable=False),
        sa.Column("created", sa.Float(), nullable=False),
        sa.Column("last_seen", sa.Float(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("authenticated", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "settings_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO settings_overrides (id) VALUES (1)")


def downgrade():
    op.drop_table("settings_overrides")
    op.drop_table("admin_sessions")
    op.drop_table("admin_state")
