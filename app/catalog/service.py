from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.catalog.models import Movie, MovieCredit, MovieGenre, ProfileMovieRating
from app.config import get_settings
from app.profiles.models import Profile
from app.providers.metadata.base import MovieDetails, MovieSearchResult
from app.providers.metadata.tmdb import TMDbProvider


def provider() -> TMDbProvider:
    return TMDbProvider(get_settings())


def search_movies(query: str) -> list[MovieSearchResult]:
    if not query.strip():
        return []
    return provider().search_movies(query.strip())


def get_or_fetch_movie(db: Session, tmdb_id: int) -> Movie:
    movie = db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
    if movie is not None:
        return movie
    details = provider().get_movie(tmdb_id)
    movie = _store_movie(db, details)
    db.commit()
    db.refresh(movie)
    return movie


def get_movie(db: Session, movie_id: int) -> Movie | None:
    return db.get(Movie, movie_id)


def get_profile_rating(db: Session, profile_id: int, movie_id: int) -> ProfileMovieRating | None:
    return db.scalar(
        select(ProfileMovieRating).where(
            ProfileMovieRating.profile_id == profile_id,
            ProfileMovieRating.movie_id == movie_id,
        )
    )


def list_profile_movies(db: Session, profile_id: int) -> list[ProfileMovieRating]:
    return list(
        db.scalars(
            select(ProfileMovieRating)
            .where(ProfileMovieRating.profile_id == profile_id)
            .order_by(ProfileMovieRating.updated_at.desc())
        ).all()
    )


def profile_taste_summary(db: Session, profile_id: int) -> dict:
    """Build a small, deterministic taste summary from explicit positive ratings.

    This is deliberately simple in M3: no ML and no recency weighting. A normal
    positive rating counts as 1, a heart as 2, and a favourite adds 2 more.
    Negative/vetoed movies never contribute positive taste signals.
    """
    ratings = list_profile_movies(db, profile_id)

    genre_scores: dict[str, float] = defaultdict(float)
    actor_scores: dict[str, float] = defaultdict(float)
    director_scores: dict[str, float] = defaultdict(float)

    for item in ratings:
        if item.veto or item.rating is None or item.rating <= 0:
            continue

        weight = 1.0 if item.rating == 1 else 2.0
        if item.favorite:
            weight += 2.0

        for genre in item.movie.genres:
            genre_scores[genre.name] += weight

        for credit in item.movie.credits:
            if credit.role_type == "director":
                director_scores[credit.name] += weight
            elif credit.role_type == "actor" and (credit.billing_order is None or credit.billing_order < 3):
                actor_scores[credit.name] += weight

    def top(scores: dict[str, float], limit: int) -> list[dict]:
        ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0].lower()))
        return [{"name": name, "score": score} for name, score in ordered[:limit]]

    return {
        "genres": top(genre_scores, 5),
        "directors": top(director_scores, 4),
        "actors": top(actor_scores, 6),
    }


def save_profile_rating(
    db: Session,
    profile: Profile,
    movie: Movie,
    *,
    rating: int | None,
    favorite: bool,
    rewatchable: bool,
    veto: bool,
) -> ProfileMovieRating:
    record = get_profile_rating(db, profile.id, movie.id)
    if record is None:
        record = ProfileMovieRating(profile_id=profile.id, movie_id=movie.id)
        db.add(record)
    record.seen = True
    record.rating = rating
    record.favorite = favorite
    record.rewatchable = rewatchable
    record.veto = veto
    db.commit()
    db.refresh(record)
    return record


def remove_profile_rating(db: Session, profile_id: int, movie_id: int) -> None:
    db.execute(
        delete(ProfileMovieRating).where(
            ProfileMovieRating.profile_id == profile_id,
            ProfileMovieRating.movie_id == movie_id,
        )
    )
    db.commit()


def _store_movie(db: Session, details: MovieDetails) -> Movie:
    movie = Movie(
        tmdb_id=details.tmdb_id,
        title=details.title,
        original_title=details.original_title,
        release_year=details.release_year,
        release_date=details.release_date,
        runtime_minutes=details.runtime_minutes,
        original_language=details.original_language,
        overview=details.overview,
        poster_path=details.poster_path,
        adult=details.adult,
        metadata_source="tmdb",
    )
    movie.genres = [
        MovieGenre(tmdb_genre_id=genre.tmdb_genre_id, name=genre.name) for genre in details.genres
    ]
    movie.credits = [
        MovieCredit(
            tmdb_person_id=credit.tmdb_person_id,
            name=credit.name,
            role_type=credit.role_type,
            character=credit.character,
            billing_order=credit.billing_order,
        )
        for credit in details.credits
    ]
    db.add(movie)
    db.flush()
    return movie
