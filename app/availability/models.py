from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MovieAvailabilityCache(Base):
    __tablename__ = "movie_availability_cache"
    __table_args__ = (
        UniqueConstraint("movie_id", "country", "provider_id", "access_type", name="uq_movie_availability"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    country: Mapped[str] = mapped_column(String(4), nullable=False)
    provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    access_type: Mapped[str] = mapped_column(String(20), nullable=False)
    logo_path: Mapped[str | None] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    movie = relationship("Movie")


class MovieAvailabilityFetch(Base):
    __tablename__ = "movie_availability_fetches"
    __table_args__ = (
        UniqueConstraint("movie_id", "country", name="uq_movie_availability_fetch"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    country: Mapped[str] = mapped_column(String(4), nullable=False)
    source_link: Mapped[str | None] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
