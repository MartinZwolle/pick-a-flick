Pick a Flick M4 update

Adds:
- onboarding for new profiles
- 20 dynamically selected anchor films, influenced only by birth year for recognizability
- ❤️ / 👍 / 😐 / 👎 / not seen onboarding choices
- manual 3–5 favourite-film step
- resumable onboarding
- migration 0003; existing profiles are grandfathered as completed
- app version 0.4.0
- README brought up to M4
- director taste display raised from 4 to 6, so tied favourites such as Tarantino are no longer silently cut off

Install:
Extract over the root of your local pick-a-flick repository.

Then:
  git status
  git add .
  git commit -m "Add taste onboarding M4"
  git push origin main

Komodo:
Deploy normally. Pre Build Images should remain enabled.
Migration 0003 runs on startup; the startup script already makes its pre-migration SQLite safety copy.
