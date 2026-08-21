from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from acquisition_launchpad.db import Base, get_session
from acquisition_launchpad.main import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fixture_payload() -> dict[str, Any]:
    raw = (ROOT / "fixtures" / "horizon_acquisition_v1.json").read_text(encoding="utf-8")
    return json.loads(raw)  # type: ignore[no-any-return]


@pytest.fixture
def sqlite_engine() -> Generator[Engine]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(sqlite_engine: Engine) -> Generator[Session]:
    factory = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


@pytest.fixture
def client(sqlite_engine: Engine) -> Generator[TestClient]:
    factory = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    application = create_app()

    def override_session() -> Generator[Session]:
        with factory() as database_session:
            yield database_session

    application.dependency_overrides[get_session] = override_session
    with TestClient(application) as test_client:
        yield test_client
