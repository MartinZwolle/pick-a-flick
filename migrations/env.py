from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.catalog.models import Movie, MovieCredit, MovieGenre, ProfileMovieRating  # noqa: F401
from app.availability.models import MovieAvailabilityCache, MovieAvailabilityFetch  # noqa: F401
from app.config import get_data_dir
from app.database import Base
from app.onboarding.models import ProfileOnboardingResponse  # noqa: F401
from app.profiles.models import Profile  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", f"sqlite:///{get_data_dir() / 'pickaflick.db'}")
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from app.movie_night.models import MovieNight, MovieNightViewer, MovieNightCandidate, GroupMovieVeto  # noqa: F401

from app.movie_night.models import WatchEvent, WatchParticipant  # noqa: F401
