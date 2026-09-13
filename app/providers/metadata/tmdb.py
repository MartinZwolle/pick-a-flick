from __future__ import annotations

import httpx

from app.config import Settings
from app.providers.metadata.base import CreditData, GenreData, MovieDetails, MovieSearchResult


class TMDbError(RuntimeError):
    pass


class TMDbProvider:
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.tmdb_api_key
        if not self.api_key:
            raise TMDbError("TMDB_API_KEY is niet ingesteld.")

    def _get(self, path: str, params: dict | None = None) -> dict:
        query = {"api_key": self.api_key, **(params or {})}
        try:
            response = httpx.get(
                f"{self.BASE_URL}{path}",
                params=query,
                timeout=10.0,
                headers={"Accept": "application/json", "User-Agent": "Pick-a-Flick/0.2"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TMDbError(f"TMDb kon niet worden bereikt: {exc}") from exc
        return response.json()

    def search_movies(self, query: str) -> list[MovieSearchResult]:
        payload = self._get(
            "/search/movie",
            {
                "query": query,
                "include_adult": str(self.settings.household.adult_content).lower(),
                "language": "nl-NL",
                "region": self.settings.household.country,
            },
        )
        results: list[MovieSearchResult] = []
        for item in payload.get("results", []):
            release_date = item.get("release_date") or None
            release_year = _year(release_date)
            if release_year and release_year < self.settings.household.earliest_movie_year:
                continue
            if item.get("adult") and not self.settings.household.adult_content:
                continue
            results.append(
                MovieSearchResult(
                    tmdb_id=item["id"],
                    title=item.get("title") or item.get("original_title") or "Onbekende titel",
                    original_title=item.get("original_title"),
                    release_date=release_date,
                    release_year=release_year,
                    original_language=item.get("original_language"),
                    overview=item.get("overview") or None,
                    poster_path=item.get("poster_path"),
                    adult=bool(item.get("adult", False)),
                )
            )
        return results[:20]

    def get_movie(self, external_id: int) -> MovieDetails:
        item = self._get(
            f"/movie/{external_id}",
            {"append_to_response": "credits", "language": "nl-NL"},
        )
        release_date = item.get("release_date") or None
        cast = sorted(item.get("credits", {}).get("cast", []), key=lambda c: c.get("order", 999))[:8]
        crew = item.get("credits", {}).get("crew", [])
        directors = [person for person in crew if person.get("job") == "Director"][:3]
        credits = [
            CreditData(
                tmdb_person_id=person["id"],
                name=person.get("name") or "Onbekend",
                role_type="actor",
                character=person.get("character") or None,
                billing_order=person.get("order"),
            )
            for person in cast
        ]
        credits.extend(
            CreditData(
                tmdb_person_id=person["id"],
                name=person.get("name") or "Onbekend",
                role_type="director",
            )
            for person in directors
        )
        return MovieDetails(
            tmdb_id=item["id"],
            title=item.get("title") or item.get("original_title") or "Onbekende titel",
            original_title=item.get("original_title"),
            release_date=release_date,
            release_year=_year(release_date),
            runtime_minutes=item.get("runtime"),
            original_language=item.get("original_language"),
            overview=item.get("overview") or None,
            poster_path=item.get("poster_path"),
            adult=bool(item.get("adult", False)),
            genres=[GenreData(tmdb_genre_id=g["id"], name=g["name"]) for g in item.get("genres", [])],
            credits=credits,
        )


def _year(release_date: str | None) -> int | None:
    if not release_date or len(release_date) < 4:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None
