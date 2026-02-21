import json
import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/groundwork_test")
os.environ.setdefault("PERPLEXITY_API_KEY", "test-pplx-key")
os.environ.setdefault("ADMIN_API_KEY", "test-key")
os.environ.setdefault("VERIFY_GENERATED_URLS", "false")

from app.db import get_db
from app.main import app
from app.models import City

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
CITY_FIXTURE_FILES = {
    ("barcelona", "spain"): "barcelona.json",
    ("milan", "italy"): "milan.json",
    ("new york city", "united states"): "new-york-city.json",
    ("london", "united kingdom"): "london.json",
    ("riga", "latvia"): "riga-latvia.json",
}


def _load_fixture_payload(filename: str) -> dict:
    fixture_path = FIXTURES_DIR / filename
    return json.loads(fixture_path.read_text())


@pytest.fixture(scope="session")
def engine():
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url, future=True)
    migration_dir = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
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
    payload = _load_fixture_payload("barcelona.json")

    httpx_mock.add_response(
        method="POST",
        url="https://api.perplexity.ai/chat/completions",
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        status_code=200,
    )


@pytest.fixture()
def mock_perplexity_response_by_city(httpx_mock):
    payload_by_city = {
        key: _load_fixture_payload(filename) for key, filename in CITY_FIXTURE_FILES.items()
    }

    def _callback(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        messages = body.get("messages") or []
        city_key = ("barcelona", "spain")

        marker = "Generate transport intelligence JSON for "
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            content = str(message.get("content", ""))
            if marker not in content:
                continue

            city_part = content.split(marker, 1)[1]
            city_country = city_part.split(". Practical guidance", 1)[0]
            if "," in city_country:
                city_name, country = city_country.split(",", 1)
                candidate = (city_name.strip().lower(), country.strip().lower())
                if candidate in payload_by_city:
                    city_key = candidate
            break

        payload = payload_by_city[city_key]
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    httpx_mock.add_callback(
        _callback,
        method="POST",
        url="https://api.perplexity.ai/chat/completions",
    )


@pytest.fixture()
def sample_city(db_session):
    intel = _load_fixture_payload("barcelona.json")

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
