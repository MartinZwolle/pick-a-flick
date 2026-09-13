from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_data_dir


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    db_path = get_data_dir() / "pickaflick.db"
    return f"sqlite:///{db_path}"


engine = create_engine(
    database_url(),
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
