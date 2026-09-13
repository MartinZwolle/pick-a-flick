#!/bin/sh
set -eu

mkdir -p "${PICKAFLICK_DATA_DIR:-/data}"

# Make a lightweight pre-migration safety copy when a DB already exists.
DB="${PICKAFLICK_DATA_DIR:-/data}/pickaflick.db"
if [ -f "$DB" ]; then
  cp "$DB" "${DB}.pre-migration.bak"
fi

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
