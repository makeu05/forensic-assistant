import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./forensic.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns(eng) -> None:
    """Tiny forward-only migration for columns added after the first release (Alembic comes later)."""
    insp = inspect(eng)
    if "cases" in insp.get_table_names() and "owner_id" not in {c["name"] for c in insp.get_columns("cases")}:
        with eng.begin() as conn:
            conn.execute(text("ALTER TABLE cases ADD COLUMN owner_id INTEGER"))
