"""M13 appointments and durable Telegram outbox."""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE planning_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), timezone TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 0, token TEXT NOT NULL DEFAULT '',
        chat_id TEXT NOT NULL DEFAULT '', base_url TEXT NOT NULL DEFAULT '',
        revision INTEGER NOT NULL DEFAULT 0)""")
    op.execute("INSERT INTO planning_settings(id, timezone) VALUES(1, 'Europe/Amsterdam')")
    op.execute("""CREATE TABLE appointments (
        night_id INTEGER PRIMARY KEY REFERENCES movie_nights(id) ON DELETE CASCADE,
        starts_at REAL NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0,
        revision INTEGER NOT NULL DEFAULT 1)""")
    op.execute("""CREATE TABLE notifications (
        id INTEGER PRIMARY KEY, night_id INTEGER NOT NULL,
        revision INTEGER NOT NULL, kind TEXT NOT NULL, due_at REAL NOT NULL,
        expires_at REAL NOT NULL, message TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending',
        UNIQUE(night_id, revision, kind))""")
    op.execute("CREATE INDEX ix_notifications_due ON notifications(state, due_at)")


def downgrade():
    op.drop_table("notifications")
    op.drop_table("appointments")
    op.drop_table("planning_settings")
