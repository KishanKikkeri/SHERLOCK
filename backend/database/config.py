"""
SHERLOCK — Database configuration.

Defaults to a local SQLite file so the backend can be stood up with zero
external dependencies during early development. Set DATABASE_URL to point
at Postgres for the "real" deployment, e.g.:

    export DATABASE_URL="postgresql+psycopg2://sherlock:sherlock@localhost:5432/sherlock"

Everything else in the app should import `engine`, `SessionLocal`, and
`Base` from here rather than constructing its own connection.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(os.path.dirname(__file__), "..", "..", "sherlock.db"),
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db():
    """FastAPI-style dependency / generic context manager for a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
