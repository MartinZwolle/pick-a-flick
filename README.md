# Pick a Flick

> Stop scrolling. Start watching.

Pick a Flick is a self-hosted movie-night decision helper. Instead of endlessly scrolling through streaming catalogues, your household can discover films, compare candidates, and decide what to watch together.

## What it does

- **Profiles:** create a profile for each viewer, with personal ratings, favourites, rewatchables and film-specific vetoes.
- **Taste onboarding:** rate 20 recognisable films, then add 3–5 personal favourites.
- **Movie search:** find films through TMDb and add your own ratings.
- **Availability:** check Dutch streaming providers against your household subscriptions and rental options using TMDb watch-provider data.
- **Movie Night:** select the viewers, mood and runtime; explore recommendations, shortlist finalists and choose together.
- **Discovery:** try Surprise, Hidden Gems, Missed My Era or Rewatch modes.
- **After watching:** record whether you watched the film and let each participant rate it separately.
- **Explainable recommendations:** local taste-based ranking, without requiring an LLM.

Pick a Flick is a single-household application. This release has no individual account login or built-in admin login; protect your deployment with an access-control layer if you expose it outside your trusted network.

## Requirements

- Docker Engine with Docker Compose
- A TMDb v3 API key
- Internet access for TMDb requests and poster images

## Install

Clone the repository and prepare your local configuration:

```bash
git clone https://github.com/MartinZwolle/pick-a-flick.git
cd pick-a-flick
cp config.example.yaml config.yaml
cp .env.example .env
mkdir -p data
```

Edit `.env` and set your TMDb API key:

```dotenv
TMDB_API_KEY=your-tmdb-v3-api-key
```

Edit `config.yaml` to select your country, preferred/allowed languages, streaming subscriptions, rental providers and earliest movie year. Provider identifiers must match those supported by the application; start with the values in `config.example.yaml`.

Start the app:

```bash
docker compose up -d --build
```

Open **http://localhost:8089** on the Docker host. From another device, use the host's LAN address and port 8089.

Useful checks:

```bash
docker compose ps
docker compose logs -f pick-a-flick
```

- Health endpoint: `http://localhost:8089/health`
- Prometheus metrics: `http://localhost:8089/metrics`

The Compose file publishes port 8089 on the host and mounts `config.yaml` read-only and `./data` persistently.

**Security:** no application-level login is provided in this release. Do not publish the app or `/metrics` directly to the internet without appropriate access controls.


## Prebuilt GHCR image

After a version has been published, you can run it without building locally.
Prepare `config.yaml`, `.env` and `data` as described above, then add a
published version to `.env` (the example below is not a promise that this
version already exists):

```dotenv
PICKAFLICK_VERSION=0.10.0
```

Use the standalone registry Compose file for every command:

```bash
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up -d
docker compose -f compose.ghcr.yaml ps
docker compose -f compose.ghcr.yaml logs -f pick-a-flick
```

The image is `ghcr.io/martinzwolle/pick-a-flick:<version>` for
`linux/amd64`. Configuration, port 8089, health checks and persistent data
mounts match the local-build Compose file. Do not run both Compose variants
at the same time. For an update, back up data and configuration, change
`PICKAFLICK_VERSION`, then repeat `pull` and `up -d`. Startup runs database
migrations; restoring an older image alone may not undo a database migration.

### Publishing policy (maintainers)

The Container workflow validates pull requests without logging in or pushing.
It runs pytest, Ruff, Compose validation, a Docker build and a container
health check after startup migrations. A push of a stable tag matching
`vMAJOR.MINOR.PATCH` reruns these checks, verifies that the tagged commit is
on `main`, then publishes exactly `MAJOR.MINOR.PATCH`. Prerelease and other
tag formats are rejected. There are no `main`, `latest`, major or minor
aliases. Treat published version tags as immutable: never move or reuse a
release tag. For strict deployment pinning, use the image digest shown in GHCR.

After merging the workflow PR and reviewing the green CI for the intended
commit on `main`, a maintainer can create and push a new release tag:

```bash
git checkout main
git pull --ff-only
git tag v0.10.0
git push origin v0.10.0
```

Choose an unused version; the commands above are examples. Tagging is a
separate release action, not part of merging this change. Check the Container
workflow and the repository's Packages page after publishing.

Authentication uses the automatic `GITHUB_TOKEN`; no personal access token
or repository secret is needed for publishing. Only the publish job has
`packages: write`; validation has `contents: read`. Actions are pinned to
commit SHAs and checkout does not persist credentials.

GHCR packages are initially private. After the first successful publication,
a maintainer must set the package visibility to **Public** in package
settings to allow anonymous pulls. A public repository alone does not make
its package public. Until then, authorized users need `docker login ghcr.io`
with a token that has `read:packages`. If an existing package rejects
publishing, check its Actions access for this repository.
See [GitHub's Container registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## First movie night

1. Open **Profiles** and create a profile for each viewer.
2. Complete onboarding: rate 20 anchor films, then select 3–5 favourites.
3. Add ratings or vetoes for any other films you know.
4. Start **Movie Night** and select who is watching.
5. Choose your mood, runtime and discovery mode; review the suggested films.
6. Mark candidates, compare finalists and select your film.
7. After watching, let each viewer rate the film individually.

A film-specific personal veto is a hard exclusion for that viewer. Group feedback from a movie night is kept separate from individual post-watch ratings.

## Configuration and data

- `config.example.yaml` is the committed configuration template; copy it to **`config.yaml`** for your installation.
- `.env.example` is the committed environment template; put secrets in **`.env`**.
- `./data` holds the SQLite database and persistent application data.
- Database migrations run during container startup.
- When a database already exists, the startup script creates `pickaflick.db.pre-migration.bak` before migrations. This is a safety copy, **not** a complete backup strategy.

Back up `./data` and your local configuration securely. Do not commit real credentials, personal profiles or database files.

## External data and privacy

Film metadata and watch-provider availability come from TMDb; watch-provider information is powered by JustWatch. Availability can change and should be verified on the streaming service before playback.

This product uses the TMDB API but is not endorsed or certified by TMDB.

Streaming availability data is provided by JustWatch via TMDb. Respect the relevant provider attribution and usage requirements when redistributing or deploying the app.

Pick a Flick does not send application telemetry to its author. It does make external requests to configured metadata/availability services and poster hosts.

## Development roadmap

- **M0–M2:** application foundation, profiles and TMDb catalog — complete
- **M3–M4:** taste model and onboarding — complete
- **M5–M6:** streaming availability and explainable recommender — complete
- **M7–M8:** movie-night flow and post-watch feedback — complete
- **M9:** discovery modes and recommendation refinements — complete
- **M10:** documentation, installation validation, screenshots, CI, container publishing and release preparation — in progress
- **M11 (planned):** admin login and configuration UI
- **M12 (planned):** natural-language movie discovery with optional LLM suggestions
- **M13 (planned):** scheduling and Telegram notifications
- **M14 (planned):** further stabilization and public release

## License

[GPL-3.0-or-later](LICENSE).
