from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.catalog.models import ProfileMovieRating
from app.movie_night.models import GroupMovieVeto, MovieNightViewer, WatchParticipant
from app.onboarding.models import ProfileOnboardingResponse
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
    """Permanently remove a profile and all personal data tied to it.

    We delete explicitly instead of relying only on SQLite ON DELETE CASCADE.
    This prevents a recycled profile id from inheriting stale taste data.
    """
    profile_id = profile.id

    db.execute(
        delete(ProfileOnboardingResponse).where(
            ProfileOnboardingResponse.profile_id == profile_id
        )
    )
    db.execute(
        delete(ProfileMovieRating).where(
            ProfileMovieRating.profile_id == profile_id
        )
    )
    db.execute(
        delete(WatchParticipant).where(
            WatchParticipant.profile_id == profile_id
        )
    )
    db.execute(
        delete(MovieNightViewer).where(
            MovieNightViewer.profile_id == profile_id
        )
    )

    # Group vetoes use a normalized comma-separated viewer key instead of a FK.
    token = str(profile_id)
    db.execute(
        delete(GroupMovieVeto).where(
            or_(
                GroupMovieVeto.viewer_key == token,
                GroupMovieVeto.viewer_key.like(f"{token},%"),
                GroupMovieVeto.viewer_key.like(f"%,{token}"),
                GroupMovieVeto.viewer_key.like(f"%,{token},%"),
            )
        )
    )

    db.delete(profile)
    db.commit()
