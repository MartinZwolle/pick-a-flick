from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog import service as catalog_service
from app.catalog.models import ProfileMovieRating
from app.onboarding.models import ProfileOnboardingResponse
from app.profiles.models import Profile


ANCHOR_COUNT = 20
MIN_FAVORITES = 3
TARGET_FAVORITES = 5


@dataclass(frozen=True)
class Anchor:
    tmdb_id: int
    title: str
    year: int
    bucket: str


ANCHORS = (
    Anchor(11, "Star Wars", 1977, "adventure"),
    Anchor(348, "Alien", 1979, "thriller"),
    Anchor(85, "Raiders of the Lost Ark", 1981, "adventure"),
    Anchor(78, "Blade Runner", 1982, "scifi"),
    Anchor(1091, "The Thing", 1982, "thriller"),
    Anchor(105, "Back to the Future", 1985, "comedy"),
    Anchor(562, "Die Hard", 1988, "action"),
    Anchor(639, "When Harry Met Sally...", 1989, "romance"),
    Anchor(280, "Terminator 2: Judgment Day", 1991, "action"),
    Anchor(329, "Jurassic Park", 1993, "adventure"),
    Anchor(680, "Pulp Fiction", 1994, "crime"),
    Anchor(13, "Forrest Gump", 1994, "drama"),
    Anchor(862, "Toy Story", 1995, "animation"),
    Anchor(807, "Se7en", 1995, "thriller"),
    Anchor(597, "Titanic", 1997, "romance"),
    Anchor(603, "The Matrix", 1999, "scifi"),
    Anchor(550, "Fight Club", 1999, "drama"),
    Anchor(98, "Gladiator", 2000, "action"),
    Anchor(120, "The Lord of the Rings: The Fellowship of the Ring", 2001, "fantasy"),
    Anchor(129, "Spirited Away", 2001, "animation"),
    Anchor(496, "Kill Bill: Vol. 1", 2003, "action"),
    Anchor(38, "Eternal Sunshine of the Spotless Mind", 2004, "romance"),
    Anchor(155, "The Dark Knight", 2008, "action"),
    Anchor(19995, "Avatar", 2009, "scifi"),
    Anchor(27205, "Inception", 2010, "scifi"),
    Anchor(77338, "The Intouchables", 2011, "comedy"),
    Anchor(68718, "Django Unchained", 2012, "crime"),
    Anchor(120467, "The Grand Budapest Hotel", 2014, "comedy"),
    Anchor(76341, "Mad Max: Fury Road", 2015, "action"),
    Anchor(324857, "Spider-Man: Into the Spider-Verse", 2018, "animation"),
    Anchor(496243, "Parasite", 2019, "thriller"),
    Anchor(546554, "Knives Out", 2019, "crime"),
    Anchor(438631, "Dune", 2021, "scifi"),
    Anchor(545611, "Everything Everywhere All at Once", 2022, "comedy"),
    Anchor(346698, "Barbie", 2023, "comedy"),
    Anchor(872585, "Oppenheimer", 2023, "drama"),
)


def anchor_set(profile: Profile) -> list[Anchor]:
    """Choose recognizable anchors near the profile's formative film years.

    Birth year only influences recognizability, never the resulting taste score.
    Buckets prevent a list consisting almost entirely of one kind of movie.
    """
    current_year = datetime.now().year
    target_year = min(current_year - 2, profile.birth_year + 20)

    def score(anchor: Anchor) -> tuple[int, int]:
        too_early_penalty = 18 if anchor.year < profile.birth_year + 8 else 0
        return (abs(anchor.year - target_year) + too_early_penalty, anchor.year)

    candidates = sorted(ANCHORS, key=score)
    selected: list[Anchor] = []
    bucket_counts: dict[str, int] = {}

    for anchor in candidates:
        if anchor.year > current_year:
            continue
        if bucket_counts.get(anchor.bucket, 0) >= 4:
            continue
        selected.append(anchor)
        bucket_counts[anchor.bucket] = bucket_counts.get(anchor.bucket, 0) + 1
        if len(selected) == ANCHOR_COUNT:
            break

    if len(selected) < ANCHOR_COUNT:
        selected_ids = {item.tmdb_id for item in selected}
        for anchor in candidates:
            if anchor.tmdb_id in selected_ids:
                continue
            selected.append(anchor)
            if len(selected) == ANCHOR_COUNT:
                break

    return selected


def responses(db: Session, profile_id: int) -> dict[int, str]:
    rows = db.scalars(
        select(ProfileOnboardingResponse).where(
            ProfileOnboardingResponse.profile_id == profile_id
        )
    ).all()
    return {row.tmdb_id: row.response for row in rows}


def next_anchor(db: Session, profile: Profile) -> tuple[Anchor | None, int]:
    answered = responses(db, profile.id)
    anchors = anchor_set(profile)
    for index, anchor in enumerate(anchors, start=1):
        if anchor.tmdb_id not in answered:
            return anchor, index
    return None, len(anchors)


def save_anchor_response(
    db: Session,
    profile: Profile,
    tmdb_id: int,
    response: str,
) -> None:
    if response not in {"dislike", "neutral", "like", "love", "not_seen"}:
        raise ValueError("Ongeldige onboardingrespons")

    existing = db.scalar(
        select(ProfileOnboardingResponse).where(
            ProfileOnboardingResponse.profile_id == profile.id,
            ProfileOnboardingResponse.tmdb_id == tmdb_id,
        )
    )
    if existing is None:
        existing = ProfileOnboardingResponse(
            profile_id=profile.id, tmdb_id=tmdb_id, response=response
        )
        db.add(existing)
    else:
        existing.response = response

    if response != "not_seen":
        movie = catalog_service.get_or_fetch_movie(db, tmdb_id)
        rating_map = {"dislike": -1, "neutral": 0, "like": 1, "love": 2}
        catalog_service.save_profile_rating(
            db,
            profile,
            movie,
            rating=rating_map[response],
            favorite=False,
            rewatchable=False,
            veto=False,
        )
    db.commit()


def favorite_ratings(db: Session, profile_id: int) -> list[ProfileMovieRating]:
    return list(
        db.scalars(
            select(ProfileMovieRating)
            .where(
                ProfileMovieRating.profile_id == profile_id,
                ProfileMovieRating.favorite.is_(True),
            )
            .order_by(ProfileMovieRating.updated_at.desc())
        ).all()
    )


def add_favorite(db: Session, profile: Profile, tmdb_id: int) -> None:
    movie = catalog_service.get_or_fetch_movie(db, tmdb_id)
    current = catalog_service.get_profile_rating(db, profile.id, movie.id)
    catalog_service.save_profile_rating(
        db,
        profile,
        movie,
        rating=2 if current is None or current.rating is None else max(current.rating, 2),
        favorite=True,
        rewatchable=current.rewatchable if current else False,
        veto=False,
    )


def finish(db: Session, profile: Profile) -> bool:
    if len(favorite_ratings(db, profile.id)) < MIN_FAVORITES:
        return False
    profile.onboarding_completed = True
    db.commit()
    return True
