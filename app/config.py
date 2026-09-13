from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "Pick a Flick"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"


class HouseholdConfig(BaseModel):
    country: str = "NL"
    earliest_movie_year: int = 1977
    adult_content: bool = False


class LanguagesConfig(BaseModel):
    preferred: list[str] = Field(default_factory=lambda: ["en"])
    allowed: list[str] = Field(default_factory=lambda: ["en", "nl"])


class ProviderRoleConfig(BaseModel):
    primary: str


class ProvidersConfig(BaseModel):
    metadata: ProviderRoleConfig = Field(default_factory=lambda: ProviderRoleConfig(primary="tmdb"))
    availability: ProviderRoleConfig = Field(default_factory=lambda: ProviderRoleConfig(primary="tmdb"))


class StreamingConfig(BaseModel):
    subscriptions: list[str] = Field(default_factory=list)
    rental: list[str] = Field(default_factory=list)


class RecommendationsConfig(BaseModel):
    boost_expiring_titles: bool = False


class AIConfig(BaseModel):
    enabled: bool = False
    provider: str = "openai_compatible"
    base_url: str | None = None
    api_key_env: str = "PICKAFLICK_AI_API_KEY"


class TMDbConfig(BaseModel):
    api_key_env: str = "TMDB_API_KEY"


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    household: HouseholdConfig = Field(default_factory=HouseholdConfig)
    languages: LanguagesConfig = Field(default_factory=LanguagesConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    streaming: StreamingConfig = Field(default_factory=StreamingConfig)
    recommendations: RecommendationsConfig = Field(default_factory=RecommendationsConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    tmdb: TMDbConfig = Field(default_factory=TMDbConfig)

    @property
    def tmdb_api_key(self) -> str | None:
        return os.getenv(self.tmdb.api_key_env)

    @property
    def ai_api_key(self) -> str | None:
        return os.getenv(self.ai.api_key_env)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(
            f"Config file not found: {path}. Copy config.example.yaml to config.yaml first."
        )
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    path = Path(os.getenv("PICKAFLICK_CONFIG", "config.yaml"))
    return Settings.model_validate(_load_yaml(path))


def get_data_dir() -> Path:
    path = Path(os.getenv("PICKAFLICK_DATA_DIR", "./data"))
    path.mkdir(parents=True, exist_ok=True)
    return path
