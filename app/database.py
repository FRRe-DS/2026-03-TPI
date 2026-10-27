from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _create_engine(database_url: str) -> Engine:
    engine_options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **engine_options)


SQLALCHEMY_DATABASE_URL = get_settings().database_url
engine = _create_engine(SQLALCHEMY_DATABASE_URL) if SQLALCHEMY_DATABASE_URL else None
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    if engine is None:
        raise RuntimeError(
            "DATABASE_URL debe configurarse antes de abrir una sesión de base de datos."
        )

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
