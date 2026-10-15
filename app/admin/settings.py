from __future__ import annotations

import json
import sqlite3
from datetime import date

import pycountry
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import Settings, get_data_dir

FIELDS = {
    "country": ("Land", "household.country"),
    "preferred": ("Voorkeurstalen", "languages.preferred"),
    "allowed": ("Toegestane talen", "languages.allowed"),
    "subscriptions": ("Streamingabonnementen", "streaming.subscriptions"),
    "rental": ("Huurproviders", "streaming.rental"),
    "earliest_movie_year": ("Vroegste filmjaar", "household.earliest_movie_year"),
    "adult_content": ("Volwassen inhoud", "household.adult_content"),
}
LIST_FIELDS = {"preferred", "allowed", "subscriptions", "rental"}


class WebSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    country: str
    preferred: list[str] = Field(min_length=1, max_length=50)
    allowed: list[str] = Field(min_length=1, max_length=50)
    subscriptions: list[str] = Field(max_length=50)
    rental: list[str] = Field(max_length=50)
    earliest_movie_year: int = Field(ge=1874)
    adult_content: bool

    @field_validator("country")
    @classmethod
    def country_code(cls, value):
        if pycountry.countries.get(alpha_2=value) is None:
            raise ValueError("Gebruik een geldige landcode, bijvoorbeeld NL.")
        return value

    @field_validator("preferred", "allowed")
    @classmethod
    def language_codes(cls, values):
        if any(pycountry.languages.get(alpha_2=v) is None for v in values):
            raise ValueError("Gebruik geldige taalcodes, bijvoorbeeld en, nl.")
        return list(dict.fromkeys(values))

    @field_validator("subscriptions", "rental")
    @classmethod
    def provider_codes(cls, values):
        # Known aliases plus normalized names supported by the existing provider.
        import re
        if any(not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", v) for v in values):
            raise ValueError("Gebruik providercodes, bijvoorbeeld netflix of pathe_thuis.")
        return list(dict.fromkeys(values))

    @field_validator("earliest_movie_year")
    @classmethod
    def year(cls, value):
        if value > date.today().year:
            raise ValueError("Het filmjaar mag niet in de toekomst liggen.")
        return value

    @model_validator(mode="after")
    def languages_match(self):
        if not set(self.preferred) <= set(self.allowed):
            raise ValueError("Voorkeurstalen moeten ook bij toegestane talen staan.")
        return self


def values_from(settings: Settings) -> dict:
    result = {}
    for name, (_, path) in FIELDS.items():
        section, key = path.split(".")
        result[name] = getattr(getattr(settings, section), key)
    return result


def merge(base: Settings, overrides: dict) -> Settings:
    if not overrides:
        return base.model_copy(deep=True)
    # Validate only when overrides exist; unchanged legacy YAML retains its behavior.
    values = WebSettings.model_validate(values_from(base) | overrides).model_dump()
    data = base.model_dump()
    for name in overrides:
        section, key = FIELDS[name][1].split(".")
        data[section][key] = values[name]
    return Settings.model_validate(data)


def read_overrides() -> tuple[dict, int]:
    path = get_data_dir() / "pickaflick.db"
    if not path.exists():
        return {}, 0
    # Read-only connection must not create or migrate a database during import.
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT payload, revision FROM settings_overrides WHERE id=1"
        ).fetchone()
        return (json.loads(row[0]), row[1]) if row else ({}, 0)
    except sqlite3.OperationalError as exc:
        if "no such table: settings_overrides" in str(exc):
            return {}, 0  # Before the M11 migration only.
        raise
    finally:
        connection.close()


def effective_settings(base: Settings) -> Settings:
    return merge(base, read_overrides()[0])
