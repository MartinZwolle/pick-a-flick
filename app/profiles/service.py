from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.profiles.models import Profile


def list_profiles(db: Session) -> list[Profile]:
    return list(db.scalars(select(Profile).order_by(Profile.name)).all())


def get_profile(db: Session, profile_id: int) -> Profile | None:
    return db.get(Profile, profile_id)


def create_profile(db: Session, name: str, birth_year: int) -> Profile:
    profile = Profile(name=name.strip(), birth_year=birth_year, onboarding_completed=False)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, profile: Profile, name: str, birth_year: int) -> Profile:
    profile.name = name.strip()
    profile.birth_year = birth_year
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, profile: Profile) -> None:
    db.delete(profile)
    db.commit()
