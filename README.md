# Pick a Flick

> Stop scrolling. Start watching.

Pick a Flick is a self-hosted movie-night decision helper. Instead of endlessly scrolling through streaming catalogues, your household can discover films, compare candidates, and decide what to watch together.

## What it does

- **Profiles:** create a profile for each viewer, with personal ratings, favourites, rewatchables and film-specific vetoes.
- **Taste onboarding:** rate 20 recognisable films, then add 3–5 personal favourites.
- **Movie search:** find films through TMDb and add your own ratings.
- **Availability:** check Dutch streaming providers against your household subscriptions and rental options using TMDb watch-provider data.
- **Movie Night:** select the viewers, mood and runtime; explore recommendations, shortlist finalists and choose together.
- **AI film expert (optional):** describe your movie wish in natural language; start the same solo/group game with up to ten TMDb-verified, available films. DeepSeek, Ollama, OpenAI and Anthropic are supported.
- **Discovery:** try Surprise, Hidden Gems, Missed My Era or Rewatch modes.
- **After watching:** record whether you watched the film and let each participant rate it separately.
- **Explainable recommendations:** local taste-based ranking, without requiring an LLM.
- **Admin configuration:** one admin login for household settings, with local password setup/recovery and web overrides that preserve the YAML configuration.

Pick a Flick is a single-household application. Admin login protects configuration only; viewer profiles and movie nights have no individual account login. Protect the entire deployment with an access-control layer if you expose it outside your trusted network.

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

**Security:** admin login protects only `/admin`. Movie-night features, profiles and `/metrics` remain accessible without login. Do not publish the app directly to the internet without appropriate access controls.


## Prebuilt GHCR image

This source prepares **v0.11.0**, including M12 and DeepSeek support.
Use `ghcr.io/martinzwolle/pick-a-flick:0.11.0` only after the stable tag
has been published and its Container workflow has completed successfully.
See the [v0.11.0 release notes](docs/releases/v0.11.0.md).
The previously published v0.10.1 image does not contain M12.
Prepare `config.yaml`, `.env` and `data` as described above, then select the
published version in `.env`:

```dotenv
PICKAFLICK_VERSION=0.11.0
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

After reviewing green CI for the intended commit on `main`, create and push a
**new, unused** stable release tag matching `vMAJOR.MINOR.PATCH`.
**v0.10.1 is already published: do not recreate, move or reuse that tag.**
Tagging is a separate release action; merging a PR does not publish an image.
Check the Container workflow and the repository's Packages page after publishing.

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

## AI film expert and DeepSeek setup

AI is optional and disabled by default. It adds a source to the existing Movie Night
card game for one or more viewers; it does not add a chatbot or a separate game.
Describe your wish in natural language. After searching, the cards start directly.
Up to ten unique films are checked against TMDb titles/years and the streaming
subscriptions or rental services configured for your region. Fewer films are fine;
zero gives a clear message. Purchases and stale/error availability do not qualify.
TMDb data can lag behind the services; rental may cost extra.

For DeepSeek, add your own API key to the existing server `.env` using an editor:

```dotenv
PICKAFLICK_AI_API_KEY=your-deepseek-api-key
```

Keep the real value out of Git, chat, screenshots and shell arguments. Recreate the
container with your selected Compose file so it receives the new environment.
Then sign in to **Beheer → Instellingen**, check **Via web beheren** for these fields,
set the values and save:

| Setting | Value |
| --- | --- |
| AI-filmkenner actief | Ja |
| AI-provider | `deepseek` |
| AI-model | `deepseek-flash` |
| AI-serveradres | Leave blank; DeepSeek uses a fixed HTTPS endpoint |

The default model in an existing YAML file is not automatically changed when you
select another provider: set the DeepSeek model explicitly. Provider model IDs may
change; use a currently supported model ID for your account. The adapter uses JSON
mode, `max_tokens=4096` and disables thinking for this film selection.
The key remains server-side and is never included in the admin page or AI prompt.
The provider receives the wish, region, configured services and summarized taste;
no profile names, birth years or complete viewing history are sent.

Choose **AI-filmkenner** on Movie Night, select the viewers and describe your wish.
The rotating film reel shows playful, partly prompt-dependent texts without a
fictional progress percentage. Creative interpretations are labelled on the cards.
To stop using AI, turn it off in Beheer; ordinary discovery keeps working.

For Ollama, OpenAI, Anthropic, compatible endpoints, timeouts and limitations, see
[the M12 settings guide](docs/M12.md). Cloud provider tests use simulated responses;
a real request still needs your configured key and account credit.

## First movie night

1. Open **Profiles** and create a profile for each viewer.
2. Complete onboarding: rate 20 anchor films, then select 3–5 favourites.
3. Add ratings or vetoes for any other films you know.
4. Start **Movie Night** and select who is watching.
5. Choose your mood, runtime and discovery mode; review the suggested films.
6. Mark candidates, compare finalists and select your film.
7. After watching, let each viewer rate the film individually.

In the ordinary discovery modes, a film-specific personal veto is a hard exclusion for that viewer. In the AI source, taste, previous viewing and vetoes are soft signals; they do not exclude a film. Group feedback from a movie night is kept separate from individual post-watch ratings.

## Configuration and data

- `config.example.yaml` is the committed configuration template; copy it to **`config.yaml`** for your installation.
- `.env.example` is the committed environment template; put secrets in **`.env`**.
- `./data` holds the SQLite database and persistent application data.
- Database migrations run during container startup.
- When a database already exists, the startup script creates `pickaflick.db.pre-migration.bak` before migrations. This is a safety copy, **not** a complete backup strategy.

Back up `./data` and your local configuration securely. Do not commit real credentials, personal profiles or database files.


## Admin setup and web configuration

M11 was merged in [PR #4](https://github.com/MartinZwolle/pick-a-flick/pull/4).
The instructions below apply to the source on `main` and images built from it;
v0.9.0 predates M11, while v0.10.0 contains an HTTP admin-login bug fixed in
[PR #7](https://github.com/MartinZwolle/pick-a-flick/pull/7). For HTTP administration,
use the published v0.10.1 release or build from main with the fix.
See [the v0.10.1 notes](docs/releases/v0.10.1.md). Merging does not publish a new
image or update an existing installation.

Admin is optional for ordinary household use. There is one administrator; no
registration, roles or separate viewer accounts. Open **Beheer** to manage country,
languages, streaming subscriptions, rental providers, earliest movie year and adult
content, plus AI enablement, provider, model and an optional local/compatible endpoint. API keys remain in `.env`.

Existing limitation: the movie search/recommender does not yet use preferred/allowed
language values as filters. M11 stores and exposes these settings without changing
movie ranking; the admin page explains this.

After startup migrations, create the admin password interactively:

```bash
docker compose exec pick-a-flick python -m app.admin.cli set-password
```

For a registry deployment, use `docker compose -f compose.ghcr.yaml exec` instead.
Enter a password of 15–128 characters twice. Only a salted Argon2id hash is stored
in the persistent database. Do not put the password in shell arguments or `.env`.

**HTTPS is required for administration by default.** With a reverse proxy, restrict
direct access to the application and configure Uvicorn's `FORWARDED_ALLOW_IPS` to
trust only that proxy's address. Do not blindly trust forwarded headers from all clients.

For direct HTTP access on your **trusted home network**, explicitly add this to
`.env` and recreate the app container using your chosen Compose file:

```dotenv
PICKAFLICK_ADMIN_ALLOW_HTTP=true
```

For the local-build variant:

```bash
docker compose up -d
```

HTTP sends the admin password and session without transport encryption. Keep this
exception limited to your trusted network. HTTPS connections still get Secure cookies.

Open `/admin/login`. Sessions end after 30 minutes idle or 12 hours total.
Five password attempts in 15 minutes trigger a 15-minute cooldown across browsers.
Change your password in the web interface; this logs out every admin session.
If you forget it, reset it locally:

```bash
docker compose exec pick-a-flick python -m app.admin.cli reset-password
```

Reset also ends all sessions and clears the login cooldown. These commands require
the same persistent data volume as the running app. There is no public setup/reset page.

### Configuration precedence and upgrades

`config.yaml` stays read-only and supplies the base values. In the web interface,
check **Via web beheren** for each field you want to override. Overrides are stored
transactionally in SQLite and take effect on new requests across workers.
Uncheck a field to return it to the YAML value. A conflicting save from an older
browser tab asks you to reload. Existing film-night candidates are retained.

Back up the SQLite database consistently while writes are stopped, together with
`config.yaml` and `.env`, before upgrading from v0.9.0. Migration 0008 adds admin
and settings tables without changing household data. No default password or web
override is created. Ordinary use works before setting up admin.

To roll back safely, stop the new version, restore the pre-upgrade backup and start
the previous pinned image. Do not run old and new versions against the same database.
Restoring only an image does not restore web settings or reverse a migration.
See [the M11 design and verification notes](docs/M11.md) for details.

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
- **M10:** documentation, installation validation, screenshots, CI, container publishing and release preparation — complete
- **M11:** admin login and configuration UI — complete; merged in [PR #4](https://github.com/MartinZwolle/pick-a-flick/pull/4)
- **M12:** AI film expert as a source for the existing solo/group game, including DeepSeek — complete; merged in [PR #10](https://github.com/MartinZwolle/pick-a-flick/pull/10)
- **M13 (planned):** scheduling and Telegram notifications
- **M14 (planned):** further stabilization and public release

## License

[GPL-3.0-or-later](LICENSE).
