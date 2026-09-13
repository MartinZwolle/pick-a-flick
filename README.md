# Pick a Flick

> Stop scrolling. Start watching.

Pick a Flick is a self-hosted movie-night decision helper. It is designed to help a household discover and choose a film together, rather than endlessly browse streaming catalogs.

This repository currently contains the **M0 + M1 scaffold**:

- FastAPI application
- server-rendered mobile-first UI
- SQLite persistence
- Alembic migrations at startup
- profile create/read/update/delete
- structured JSON logging
- `/health`
- Prometheus `/metrics`
- Docker + Compose

## Quick start

```bash
cp config.example.yaml config.yaml
cp .env.example .env
mkdir -p data
docker compose up -d --build
```

Open: `http://localhost:8089`

Health: `http://localhost:8089/health`

Metrics: `http://localhost:8089/metrics`

## Persistent data

Everything persistent lives in `./data`. Back up that directory together with `config.yaml`.

The startup script makes `pickaflick.db.pre-migration.bak` before running migrations if a database already exists. This is only a migration safety copy, not a backup strategy.

## Configuration

V1 household/system settings live in `config.yaml`. Secrets are read from environment variables; do not commit `.env`.

Profile data lives in SQLite and is managed from the web UI.

## Roadmap

- **M2** Catalog + TMDb adapter
- **M3** Ratings, favourites, rewatchable, veto
- **M4** Taste onboarding
- **M5** Streaming availability
- **M6** Explainable recommender
- **M7** Movie Night flow
- **M8** Post-watch feedback
- **M9** Surprise / Hidden Gems / Missed My Era / Rewatch modes
- **M10** public v1 polish

## Privacy

Pick a Flick has no telemetry. It only talks to external services that are required for configured functionality.

## License

GPL-3.0-or-later.
