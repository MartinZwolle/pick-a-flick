# Pick a Flick

> Stop scrolling. Start watching.

Pick a Flick is a self-hosted movie-night decision helper. It helps a household discover and choose a film together instead of endlessly browsing streaming catalogues.

This repository currently contains **M0 through M5**:
- FastAPI application
- server-rendered mobile-first UI
- SQLite persistence
- Alembic migrations at startup
- profile create/read/update/delete
- TMDb movie search and details
- local movie metadata cache (SQLite)
- personal taste signals: rating, favourite, rewatchable and veto
- deterministic, explainable taste summary for genres, actors and directors
- taste onboarding with 20 age-relevant anchor films
- Dutch streaming availability via TMDb/JustWatch, matched to household subscriptions and rental fallbacks
- 3–5 manually chosen absolute favourites after onboarding
- structured JSON logging
- `/health`
- Prometheus `/metrics`
- Docker + Compose

## Quick start

```bash
cp config.example.yaml config.yaml
cp .env.example .env
mkdir -p data
# Put your TMDb v3 API key in .env
docker compose up -d --build
```

Open: `http://localhost:8089`

Health: `http://localhost:8089/health`

Metrics: `http://localhost:8089/metrics`

## TMDb

Set the v3 API key as:

```text
TMDB_API_KEY=your-key
```

The key is a secret and must not be committed. The application caches only movies that are actually opened from search results or onboarding; it does not mirror the TMDb catalogue.

Pick a Flick uses the TMDB API but is not endorsed or certified by TMDB.

## Taste onboarding

New profiles run through a short onboarding:
1. Rate 20 recognizable anchor films with ❤️ / 👍 / 😐 / 👎 / not seen.
2. Search for at least 3 (ideally 5) absolute favourites.
3. Continue to the personal taste overview.

Birth year only changes which anchor films are likely to be recognizable. It is not used as a taste signal. “Not seen” is neutral.

Profiles that existed before M4 are automatically marked as already onboarded during migration.

## Persistent data

Everything persistent lives in `./data`. Back up that directory together with your installation configuration.

The startup script makes `pickaflick.db.pre-migration.bak` before running migrations when a database already exists. This is a migration safety copy, not a backup strategy.

## Configuration

V1 household/system settings live in `config.yaml`. Secrets are read from environment variables; do not commit `.env`.

Profile and cached movie data live in SQLite and are managed from the web UI.

## Roadmap

- **M0** Runtime, persistence, health and metrics ✅
- **M1** Profiles ✅
- **M2** Catalog + TMDb adapter ✅
- **M3** Richer ratings/taste model ✅
- **M4** Taste onboarding ✅
- **M5** Streaming availability ✅
- **M6** Explainable recommender
- **M7** Movie Night flow
- **M8** Post-watch feedback
- **M9** Surprise / Hidden Gems / Missed My Era / Rewatch modes
- **M10** public v1 polish

## Privacy

Pick a Flick has no telemetry. It only talks to external services required for configured functionality.

## License

GPL-3.0-or-later.
