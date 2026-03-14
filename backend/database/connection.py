import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"

# Support both the repo-level .env described in the docs and the older backend/.env.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=False)


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Example: postgresql+psycopg://localhost/spyboxd"
        )

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if database_url.startswith("postgresql://") and not database_url.startswith("postgresql+"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("sqlite"):
        raise RuntimeError(
            "SQLite runtime is no longer supported. "
            "Use PostgreSQL and the import utility for legacy SQLite data."
        )

    return database_url


DATABASE_URL = get_database_url()


def _create_engine() -> Engine:
    engine_kwargs = {"echo": False, "future": True, "pool_pre_ping": True}
    return create_engine(DATABASE_URL, **engine_kwargs)


engine = _create_engine()
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Validate connectivity and surface schema state.

    Schema changes should go through Alembic, not ad-hoc runtime ALTER TABLE calls.
    """
    from .models import Base

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    application_tables = set(Base.metadata.tables.keys())

    if not existing_tables.intersection(application_tables):
        print("⚠️  Database is reachable but has no application tables yet.")
        print("   Run `alembic upgrade head` before using the API.")
    else:
        print("✅ Database connection verified.")


if __name__ == "__main__":
    init_db()
