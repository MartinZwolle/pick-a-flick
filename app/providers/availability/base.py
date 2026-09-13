from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AvailabilityItem:
    provider_id: int
    provider_name: str
    provider_slug: str
    access_type: str  # subscription / rent / buy
    logo_path: str | None = None

    @property
    def logo_url(self) -> str | None:
        if not self.logo_path:
            return None
        return f"https://image.tmdb.org/t/p/w92{self.logo_path}"


@dataclass(frozen=True)
class MovieAvailability:
    country: str
    items: list[AvailabilityItem]
    source: str = "tmdb"
    source_link: str | None = None
