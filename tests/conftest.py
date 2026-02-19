import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/groundwork_test")
os.environ.setdefault("PERPLEXITY_API_KEY", "test-pplx-key")
os.environ.setdefault("ADMIN_API_KEY", "test-key")

from app.db import get_db
from app.main import app
from app.models import City


@pytest.fixture(scope="session")
def engine():
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url, future=True)
    migration_dir = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
    migration_files = sorted(migration_dir.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No migration files found in {migration_dir}")

    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            for migration_file in migration_files:
                cur.execute(migration_file.read_text())
        conn.commit()
    finally:
        conn.close()

    yield engine

    cleanup = engine.raw_connection()
    try:
        cleanup.autocommit = True
        with cleanup.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS city_requests CASCADE;")
            cur.execute("DROP TABLE IF EXISTS cities CASCADE;")
    finally:
        cleanup.close()

    engine.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    test_session_local = sessionmaker(bind=connection, autocommit=False, autoflush=False, expire_on_commit=False)
    session: Session = test_session_local()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def mock_perplexity_response(httpx_mock):
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "barcelona.json"
    payload = json.loads(fixture_path.read_text())

    httpx_mock.add_response(
        method="POST",
        url="https://api.perplexity.ai/chat/completions",
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        status_code=200,
    )


@pytest.fixture()
def sample_city(db_session):
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "barcelona.json"
    intel = json.loads(fixture_path.read_text())

    city = City(
        slug="barcelona-es",
        city_name="Barcelona",
        country="Spain",
        country_code="ES",
        latitude=41.3874,
        longitude=2.1686,
        status="ready",
        intel=intel,
        raw_response=json.dumps(intel),
    )
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)
    return city
