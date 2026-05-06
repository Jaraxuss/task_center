from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

_settings = get_settings()

DATABASE_PATH: Path = _settings.database_path
DATABASE_URL: str = _settings.database_url

# Only create the parent directory for real filesystem-backed SQLite databases.
# In-memory or ":memory:" URLs have no meaningful parent directory.
if str(DATABASE_PATH) != ":memory:" and DATABASE_PATH.parent and str(DATABASE_PATH.parent) not in {"", "."}:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
