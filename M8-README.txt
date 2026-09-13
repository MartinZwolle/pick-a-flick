Pick a Flick M8 — Post-watch feedback

Built explicitly on top of M7.2 card-by-card Film Night.

After "Deze wordt het":
- "We hebben hem gekeken" opens per-viewer feedback
- each viewer can give ❤️ / 👍 / 😐 / 👎
- 🔁 Nog eens kijken updates that person's rewatch signal
- 🛑 Afgehaakt is stored separately and also acts as a negative personal signal
- one shared watch event stores movie, time and attendees
- individual ratings feed the existing personal taste profile
- blank feedback records attendance only and does not overwrite taste
- "Toch niet gekeken" stores NO watch event and NO taste data
- card-by-card M7.2 UX remains intact

Migration: 0006
Version: 0.8.0

Install over M7.2:
  git add .
  git commit -m "Add post-watch feedback M8"
  git push origin main

Then Komodo Deploy with Pre Build Images enabled.
