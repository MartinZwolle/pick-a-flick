Pick a Flick M9 — Discovery modes

Built on M8 + M7.2 card-by-card flow.

New Film Night modes:
- 🎬 Gewoon filmavond
- 🎲 Verras ons
- 💎 Pareltjes
- 📼 Gemist uit mijn tijd
- 🔁 Nog een keer

Also:
- adaptive fallback when mood/runtime is too restrictive
- hard personal and group vetoes always remain hard
- availability remains mandatory
- rewatch mode uses explicit personal rewatch flags
- "Gemist uit mijn tijd" derives a broad movie-era window from viewer birth years
- feedback checkbox flags now render as proper toggle pills
- M7.2 one-card-at-a-time UX remains intact
- M8 post-watch feedback remains intact

Migration: 0007
Version: 0.9.0

Install over M8:
  git add .
  git commit -m "Add discovery modes M9"
  git push origin main

Then Komodo Deploy with Pre Build Images enabled.
