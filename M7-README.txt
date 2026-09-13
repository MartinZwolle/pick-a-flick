Pick a Flick M7 — Filmavond

End-to-end Film Night:
- select viewers
- up to two moods, or none = surprise
- optional runtime limit
- active TMDb discovery
- NL availability gate
- hard personal vetoes excluded
- group-specific Nooit persists for exact viewer combination
- group taste scoring with Why this?
- decisions: Nooit / Nu niet / Misschien / Kanshebber / Verrassend / Deze wordt het
- selected movie ends the session
- migration 0005
- version 0.7.0

Note: first run may take several seconds because discovery fetches movie details and availability.
This patch deliberately does NOT touch app/templates/profiles/detail.html, so the profile-page repair stays intact.

Install:
git status
git add .
git commit -m "Add Film Night flow M7"
git push origin main
Then Komodo Deploy with Pre Build Images enabled.
