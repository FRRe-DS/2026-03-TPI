from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.core.config import Settings
from app.database import Base, get_db
from app.main import create_app
from app.repositories.dependencies import get_location_repository
from app.repositories.locations import LocationRepository


class ManualClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> datetime:
        self.current += delta
        return self.current


class AppFactory(Protocol):
    def __call__(
        self,
        *,
        location_repository: LocationRepository,
        clock: Callable[[], datetime],
    ) -> tuple[FastAPI, Engine]: ...


@pytest.fixture
def test_clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def test_app_factory() -> Iterator[AppFactory]:
    engines: list[Engine] = []

    def factory(
        *,
        location_repository: LocationRepository,
        clock: Callable[[], datetime],
    ) -> tuple[FastAPI, Engine]:
        test_engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        engines.append(test_engine)
        Base.metadata.create_all(test_engine)
        application = create_app(
            Settings(
                _env_file=None,
                redis_url=None,
                reservation_ttl_seconds=60,
            )
        )
        application.state.test_engine = test_engine
        application.state.database_engine = test_engine
        application.state.clock = clock
        principal = AuthenticatedPrincipal(subject=uuid4())
        application.dependency_overrides[get_authenticated_principal] = (
            lambda: principal
        )

        def override_db() -> Iterator[Session]:
            with Session(test_engine, expire_on_commit=False) as session:
                yield session

        application.dependency_overrides[get_db] = override_db
        application.dependency_overrides[get_location_repository] = (
            lambda: location_repository
        )
        return application, test_engine

    yield factory

    for test_engine in engines:
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()
