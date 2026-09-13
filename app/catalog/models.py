from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(255))
    release_year: Mapped[int | None] = mapped_column(Integer)
    release_date: Mapped[str | None] = mapped_column(String(10))
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    original_language: Mapped[str | None] = mapped_column(String(12))
    overview: Mapped[str | None] = mapped_column(Text)
    poster_path: Mapped[str | None] = mapped_column(String(255))
    adult: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_source: Mapped[str] = mapped_column(String(40), nullable=False, default="tmdb")
    metadata_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    genres: Mapped[list[MovieGenre]] = relationship(
        back_populates="movie", cascade="all, delete-orphan", lazy="selectin"
    )
    credits: Mapped[list[MovieCredit]] = relationship(
        back_populates="movie", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def poster_url(self) -> str | None:
        if not self.poster_path:
            return None
        return f"https://image.tmdb.org/t/p/w500{self.poster_path}"


class MovieGenre(Base):
    __tablename__ = "movie_genres"
    __table_args__ = (UniqueConstraint("movie_id", "tmdb_genre_id", name="uq_movie_genre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    tmdb_genre_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    movie: Mapped[Movie] = relationship(back_populates="genres")


class MovieCredit(Base):
    __tablename__ = "movie_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    tmdb_person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role_type: Mapped[str] = mapped_column(String(20), nullable=False)  # actor / director
    character: Mapped[str | None] = mapped_column(String(255))
    billing_order: Mapped[int | None] = mapped_column(Integer)

    movie: Mapped[Movie] = relationship(back_populates="credits")


class ProfileMovieRating(Base):
    __tablename__ = "profile_movie_ratings"
    __table_args__ = (UniqueConstraint("profile_id", "movie_id", name="uq_profile_movie_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    seen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rating: Mapped[int | None] = mapped_column(Integer)  # -1 / 0 / 1 / 2
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rewatchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    veto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    movie: Mapped[Movie] = relationship(lazy="joined")
