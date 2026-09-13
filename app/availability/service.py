from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.availability.models import MovieAvailabilityCache, MovieAvailabilityFetch
from app.catalog.models import Movie
from app.config import get_settings
from app.providers.availability.tmdb import TMDbAvailabilityProvider
from app.providers.metadata.tmdb import TMDbError


CACHE_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class AvailabilityView:
    subscriptions: list[MovieAvailabilityCache]
    rentals: list[MovieAvailabilityCache]
    purchases: list[MovieAvailabilityCache]
    other_subscriptions: list[MovieAvailabilityCache]
    source_link: str | None
    stale: bool
    error: str | None = None

    @property
    def watchable_now(self) -> bool:
        return bool(self.subscriptions)

    @property
    def fallback_available(self) -> bool:
        return bool(self.rentals or self.purchases)


def _fetch_record(db: Session, movie_id: int, country: str) -> MovieAvailabilityFetch | None:
    return db.scalar(
        select(MovieAvailabilityFetch).where(
            MovieAvailabilityFetch.movie_id == movie_id,
            MovieAvailabilityFetch.country == country,
        )
    )


def _rows(db: Session, movie_id: int, country: str) -> list[MovieAvailabilityCache]:
    return list(
        db.scalars(
            select(MovieAvailabilityCache).where(
                MovieAvailabilityCache.movie_id == movie_id,
                MovieAvailabilityCache.country == country,
            )
        ).all()
    )


def _is_fresh(fetch: MovieAvailabilityFetch | None) -> bool:
    if fetch is None or fetch.fetched_at is None:
        return False
    fetched = fetch.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - fetched < CACHE_TTL


def refresh(db: Session, movie: Movie) -> tuple[list[MovieAvailabilityCache], MovieAvailabilityFetch]:
    settings = get_settings()
    country = settings.household.country.upper()
    result = TMDbAvailabilityProvider(settings).get_movie_availability(movie.tmdb_id)

    db.execute(
        delete(MovieAvailabilityCache).where(
            MovieAvailabilityCache.movie_id == movie.id,
            MovieAvailabilityCache.country == country,
        )
    )
    now = datetime.now(timezone.utc)
    for item in result.items:
        db.add(
            MovieAvailabilityCache(
                movie_id=movie.id,
                country=country,
                provider_id=item.provider_id,
                provider_name=item.provider_name,
                provider_slug=item.provider_slug,
                access_type=item.access_type,
                logo_path=item.logo_path,
                fetched_at=now,
            )
        )

    fetch = _fetch_record(db, movie.id, country)
    if fetch is None:
        fetch = MovieAvailabilityFetch(
            movie_id=movie.id,
            country=country,
            source_link=result.source_link,
            fetched_at=now,
        )
        db.add(fetch)
    else:
        fetch.source_link = result.source_link
        fetch.fetched_at = now

    db.commit()
    return _rows(db, movie.id, country), fetch


def get_for_movie(db: Session, movie: Movie) -> AvailabilityView:
    settings = get_settings()
    country = settings.household.country.upper()
    fetch = _fetch_record(db, movie.id, country)
    rows = _rows(db, movie.id, country)
    stale = not _is_fresh(fetch)
    error = None

    if stale:
        try:
            rows, fetch = refresh(db, movie)
            stale = False
        except TMDbError as exc:
            # Graceful degradation: keep old rows if TMDb is temporarily down.
            error = str(exc)

    subscriptions = set(settings.streaming.subscriptions)
    rentals = set(settings.streaming.rental)

    own_subscriptions = sorted(
        [r for r in rows if r.access_type == "subscription" and r.provider_slug in subscriptions],
        key=lambda r: r.provider_name.lower(),
    )
    own_rentals = sorted(
        [r for r in rows if r.access_type == "rent" and r.provider_slug in rentals],
        key=lambda r: r.provider_name.lower(),
    )
    purchases = sorted(
        [r for r in rows if r.access_type == "buy" and r.provider_slug in rentals],
        key=lambda r: r.provider_name.lower(),
    )
    other_subscriptions = sorted(
        [r for r in rows if r.access_type == "subscription" and r.provider_slug not in subscriptions],
        key=lambda r: r.provider_name.lower(),
    )

    return AvailabilityView(
        subscriptions=own_subscriptions,
        rentals=own_rentals,
        purchases=purchases,
        other_subscriptions=other_subscriptions,
        source_link=fetch.source_link if fetch else None,
        stale=stale,
        error=error,
    )
