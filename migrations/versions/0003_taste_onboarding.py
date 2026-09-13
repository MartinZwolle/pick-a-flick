"""add taste onboarding

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "onboarding_completed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # Existing profiles already contain hand-entered taste data and should not
    # suddenly be forced through onboarding after this upgrade.
    op.execute("UPDATE profiles SET onboarding_completed = 1")

    op.create_table(
        "profile_onboarding_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("response", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "profile_id", "tmdb_id", name="uq_profile_onboarding_response"
        ),
    )
    op.create_index(
        "ix_profile_onboarding_responses_profile_id",
        "profile_onboarding_responses",
        ["profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_profile_onboarding_responses_profile_id",
        table_name="profile_onboarding_responses",
    )
    op.drop_table("profile_onboarding_responses")
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.drop_column("onboarding_completed")
