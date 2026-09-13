from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class MovieSearchResult:
    tmdb_id: int
    title: str
    original_title: str | None
    release_date: str | None
    release_year: int | None
    original_language: str | None
    overview: str | None
    poster_path: str | None
    adult: bool

    @property
    def poster_url(self) -> str | None:
        if not self.poster_path:
            return None
        return f"https://image.tmdb.org/t/p/w342{self.poster_path}"


@dataclass(slots=True)
class CreditData:
    tmdb_person_id: int
    name: str
    role_type: str
    character: str | None = None
    billing_order: int | None = None


@dataclass(slots=True)
class GenreData:
    tmdb_genre_id: int
    name: str


@dataclass(slots=True)
class MovieDetails:
    tmdb_id: int
    title: str
    original_title: str | None
    release_date: str | None
    release_year: int | None
    runtime_minutes: int | None
    original_language: str | None
    overview: str | None
    poster_path: str | None
    adult: bool
    genres: list[GenreData] = field(default_factory=list)
    credits: list[CreditData] = field(default_factory=list)


class MetadataProvider(Protocol):
    def search_movies(self, query: str) -> list[MovieSearchResult]: ...

    def get_movie(self, external_id: int) -> MovieDetails: ...
