from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    birth_year: int = Field(ge=1900, le=2100)


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    birth_year: int
    created_at: datetime
    updated_at: datetime
