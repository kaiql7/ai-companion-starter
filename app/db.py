from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for every SQLAlchemy model."""


class Database:
    """Own the engine and create short-lived database sessions.

    Keeping this in a class makes it possible for tests to create an isolated
    in-memory or temporary-file database without changing global state.
    """

    def __init__(self, url: str) -> None:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(
            url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    def create_all(self) -> None:
        # Importing models registers their tables on Base.metadata.
        from app import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def session(self) -> Generator[Session, None, None]:
        with self.session_factory() as session:
            yield session
