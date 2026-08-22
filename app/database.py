"""
This module provides database engine and session management.

It replaces Flask-SQLAlchemy with plain SQLAlchemy so that the database layer
does not depend on a web framework. The 'db' object owns the engine and the
session factory, while 'get_session' is a FastAPI dependency that yields a
session for the duration of one request.
"""

# --------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------

from typing import Any, Dict, Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool


# --------------------------------------------------------------------------------
# Declarative Base
# --------------------------------------------------------------------------------

Base = declarative_base()


# --------------------------------------------------------------------------------
# Class: Database
# --------------------------------------------------------------------------------

class Database:
  """Holds the SQLAlchemy engine and session factory for the app."""

  def __init__(self) -> None:
    self.engine: Optional[Engine] = None
    self.session_factory: Optional[sessionmaker] = None

  def init_app(self, database_uri: str) -> None:
    """Creates the engine and session factory for the given database URI."""

    kwargs: Dict[str, Any] = dict()

    if database_uri.startswith('sqlite'):
      # SQLAlchemy gives each thread its own SQLite connection by default.
      # Sync endpoints run in a thread pool, so an in-memory database would be
      # created per thread. A static pool shares one connection instead.
      kwargs['connect_args'] = {'check_same_thread': False}
      if database_uri in ('sqlite://', 'sqlite:///:memory:'):
        kwargs['poolclass'] = StaticPool

    self.engine = create_engine(database_uri, **kwargs)
    self.session_factory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

  def create_all(self) -> None:
    """Creates all tables that do not exist yet."""
    Base.metadata.create_all(self.engine)

  def drop_all(self) -> None:
    """Drops all tables."""
    Base.metadata.drop_all(self.engine)

  def session(self) -> Session:
    """Creates a new session. The caller is responsible for closing it."""
    return self.session_factory()


# --------------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------------

db = Database()


# --------------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------------

def get_session() -> Iterator[Session]:
  """Provides a database session for one request."""

  session = db.session()
  try:
    yield session
  finally:
    session.close()
