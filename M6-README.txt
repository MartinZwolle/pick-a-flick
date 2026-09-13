Pick a Flick M6 — Explainable recommender

Adds the first deterministic recommendation engine:
- scores unseen locally cached movies against personal genre/director/actor taste
- explicit favorites and hearts carry more weight
- vetoed and already seen films are excluded
- availability from M5 gates the visible results
- every recommendation explains why it scored
- no AI involved
- app version 0.6.0
- no database migration

Important M6 limitation:
The recommender intentionally works only with movies already in the local cache.
That makes the algorithm testable without pretending the cache is a full catalogue.
M7 Film Night will add active candidate discovery.

Install:
  git status
  git add .
  git commit -m "Add explainable recommender M6"
  git push origin main
Then deploy in Komodo with Pre Build Images enabled.
