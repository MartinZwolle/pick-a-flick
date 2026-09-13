Pick a Flick M5 — Streaming availability

Adds:
- TMDb watch-provider adapter (JustWatch-backed data)
- NL household matching for configured subscriptions
- rental/buy fallback matching (Pathé Thuis in the example config)
- provider normalization/slugs
- 24-hour SQLite availability cache
- stale-cache fallback if TMDb is temporarily unavailable
- provider badges on movie detail pages
- migration 0004
- app version 0.5.0

Your existing config already contains:
  subscriptions: netflix, disney_plus, prime_video
  rental: pathe_thuis

Adjust config.yaml to match the services your household actually has.

Install over your current M4 repository, then:
  git status
  git add .
  git commit -m "Add streaming availability M5"
  git push origin main

Komodo: Deploy normally with Pre Build Images enabled.
