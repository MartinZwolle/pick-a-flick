from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProfileOnboardingResponse(Base):
    __tablename__ = "profile_onboarding_responses"
    __table_args__ = (
        UniqueConstraint("profile_id", "tmdb_id", name="uq_profile_onboarding_response"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False)
    response: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
