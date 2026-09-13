from __future__ import annotations

import re

from app.config import Settings
from app.providers.availability.base import AvailabilityItem, MovieAvailability
from app.providers.metadata.tmdb import TMDbProvider


PROVIDER_ALIASES = {
    "netflix": {"netflix", "netflix basic with ads", "netflix standard with ads"},
    "disney_plus": {"disney plus", "disney+"},
    "prime_video": {"amazon prime video", "prime video", "amazon video"},
    "pathe_thuis": {"pathe thuis", "pathé thuis"},
    "hbo_max": {"hbo max", "max"},
    "videoland": {"videoland"},
    "skyshowtime": {"skyshowtime"},
    "apple_tv_plus": {"apple tv+", "apple tv plus"},
    "npo_plus": {"npo plus", "npo start plus"},
}


def provider_slug(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower().replace("é", "e")).strip()
    for slug, aliases in PROVIDER_ALIASES.items():
        if normalized in {re.sub(r"[^a-z0-9]+", " ", a.lower().replace("é", "e")).strip() for a in aliases}:
            return slug
    return normalized.replace(" ", "_")


class TMDbAvailabilityProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tmdb = TMDbProvider(settings)

    def get_movie_availability(self, tmdb_id: int) -> MovieAvailability:
        payload = self.tmdb._get(f"/movie/{tmdb_id}/watch/providers")
        country = self.settings.household.country.upper()
        region = payload.get("results", {}).get(country, {})

        items: list[AvailabilityItem] = []
        seen: set[tuple[int, str]] = set()

        # TMDb/JustWatch calls subscription streaming "flatrate".
        for source_key, access_type in (
            ("flatrate", "subscription"),
            ("rent", "rent"),
            ("buy", "buy"),
        ):
            for provider in region.get(source_key, []):
                key = (provider["provider_id"], access_type)
                if key in seen:
                    continue
                seen.add(key)
                name = provider.get("provider_name") or "Onbekende dienst"
                items.append(
                    AvailabilityItem(
                        provider_id=provider["provider_id"],
                        provider_name=name,
                        provider_slug=provider_slug(name),
                        access_type=access_type,
                        logo_path=provider.get("logo_path"),
                    )
                )

        return MovieAvailability(
            country=country,
            items=items,
            source_link=region.get("link"),
        )
