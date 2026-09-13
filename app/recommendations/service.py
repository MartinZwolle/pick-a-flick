from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.models import Movie, ProfileMovieRating
from app.profiles.models import Profile


@dataclass
class Recommendation:
    movie: Movie
    score: float
    reasons: list[str] = field(default_factory=list)
    wildcard: bool = False


def _taste(profile_ratings: list[ProfileMovieRating]) -> dict[str, dict[str, float]]:
    genres=defaultdict(float); actors=defaultdict(float); directors=defaultdict(float)
    for r in profile_ratings:
        if r.veto or r.rating is None or r.rating <= 0:
            continue
        weight=1.0 if r.rating == 1 else 2.0
        if r.favorite: weight += 2.0
        if r.rewatchable: weight += .5
        for g in r.movie.genres: genres[g.name] += weight
        for c in r.movie.credits:
            if c.role_type=="director": directors[c.name] += weight
            elif c.role_type=="actor" and (c.billing_order is None or c.billing_order < 3):
                actors[c.name] += weight
    return {"genres":genres,"actors":actors,"directors":directors}


def recommendations_for_profile(db: Session, profile: Profile, limit: int=12) -> list[Recommendation]:
    ratings=list(db.scalars(select(ProfileMovieRating).where(ProfileMovieRating.profile_id==profile.id)).all())
    seen={r.movie_id for r in ratings}
    veto={r.movie_id for r in ratings if r.veto}
    taste=_taste(ratings)

    movies=list(db.scalars(select(Movie).order_by(Movie.release_year.desc())).unique().all())
    ranked=[]
    for movie in movies:
        if movie.id in seen or movie.id in veto:
            continue
        score=0.0; reasons=[]
        genre_hits=sorted(((taste["genres"].get(g.name,0),g.name) for g in movie.genres), reverse=True)
        genre_hits=[x for x in genre_hits if x[0]>0]
        if genre_hits:
            add=min(sum(x[0] for x in genre_hits)*.55,6)
            score+=add
            reasons.append("Past bij je liefde voor "+", ".join(x[1] for x in genre_hits[:2]))
        director_hits=sorted(((taste["directors"].get(c.name,0),c.name) for c in movie.credits if c.role_type=="director"),reverse=True)
        director_hits=[x for x in director_hits if x[0]>0]
        if director_hits:
            score+=min(director_hits[0][0]*1.2,6)
            reasons.append(f"Van {director_hits[0][1]}, die vaker in je smaakprofiel voorkomt")
        actor_hits=sorted(((taste["actors"].get(c.name,0),c.name) for c in movie.credits if c.role_type=="actor"),reverse=True)
        actor_hits=[x for x in actor_hits if x[0]>0]
        if actor_hits:
            score+=min(sum(x[0] for x in actor_hits[:2])*.45,4)
            reasons.append("Met "+", ".join(x[1] for x in actor_hits[:2]))
        if score>0:
            ranked.append(Recommendation(movie=movie,score=round(score,2),reasons=reasons[:3]))
    ranked.sort(key=lambda x:(-x.score, -(x.movie.release_year or 0), x.movie.title.lower()))
    return ranked[:limit]
