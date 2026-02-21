import pytest
from sqlalchemy import select

from app.models import City, CityRequest

pytestmark = pytest.mark.integration


def _city_payload() -> dict:
    return {
        "city_name": "Barcelona",
        "country": "Spain",
        "country_code": "ES",
        "latitude": 41.3874,
        "longitude": 2.1686,
    }


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_cities_empty(client):
    response = client.get("/cities")
    assert response.status_code == 200
    assert response.json() == []


def test_get_cities_with_data(client, sample_city):
    response = client.get("/cities")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["slug"] == sample_city.slug


def test_get_city_by_slug(client, sample_city):
    response = client.get(f"/cities/{sample_city.slug}")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == sample_city.slug
    assert data["city_name"] == "Barcelona"


def test_get_city_not_found(client):
    response = client.get("/cities/does-not-exist")
    assert response.status_code == 404


def test_get_city_html(client, sample_city):
    response = client.get(f"/{sample_city.slug}")
    assert response.status_code == 200
    assert "Barcelona" in response.text
    assert "Transport Authorities" in response.text
    assert "iOS app" in response.text
    assert "Android app" in response.text
    assert "Airport info" in response.text
    assert "Open" in response.text


def test_create_city_success(client, mock_perplexity_response):
    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=_city_payload())
    assert response.status_code == 201

    data = response.json()
    assert data["slug"] == "barcelona-es"
    assert data["status"] == "ready"
    assert data["intel"] is not None
    assert data["intel"]["authorities"]


def test_create_city_custom_slug(client, mock_perplexity_response):
    payload = _city_payload()
    payload["slug"] = "barca-custom"

    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=payload)
    assert response.status_code == 201
    assert response.json()["slug"] == "barca-custom"


def test_create_city_duplicate(client, sample_city):
    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=_city_payload())
    assert response.status_code == 409


def test_create_city_retries_failed_slug(client, db_session, mock_perplexity_response):
    failed_city = City(
        slug="barcelona-es",
        city_name="Barcelona",
        country="Spain",
        country_code="ES",
        latitude=41.3874,
        longitude=2.1686,
        status="failed",
        intel=None,
        raw_response=None,
    )
    db_session.add(failed_city)
    db_session.commit()
    db_session.refresh(failed_city)

    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=_city_payload())
    assert response.status_code == 201

    data = response.json()
    assert data["slug"] == "barcelona-es"
    assert data["status"] == "ready"
    assert data["intel"] is not None

    stored = db_session.scalar(select(City).where(City.slug == "barcelona-es"))
    assert stored is not None
    assert stored.id == failed_city.id
    assert stored.status == "ready"
    assert stored.intel is not None


def test_create_city_perplexity_400_details(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.perplexity.ai/chat/completions",
        status_code=400,
        json={"error": {"message": "Malformed request payload"}},
        headers={"x-request-id": "req_test_400"},
    )

    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=_city_payload())
    assert response.status_code == 502

    detail = response.json()["detail"]
    assert "Perplexity API error 400" in detail
    assert "req_test_400" in detail
    assert "Malformed request payload" in detail


def test_create_city_no_auth(client):
    response = client.post("/cities", json=_city_payload())
    assert response.status_code == 401


def test_create_city_bad_auth(client):
    response = client.post("/cities", headers={"X-API-Key": "wrong-key"}, json=_city_payload())
    assert response.status_code == 403


def test_request_city(client, db_session):
    response = client.post("/requests", json={"raw_input": "Joburg", "email": "user@example.com"})
    assert response.status_code == 201
    assert "Thanks" in response.json()["message"]

    stored = db_session.scalar(select(CityRequest).where(CityRequest.raw_input == "Joburg"))
    assert stored is not None
    assert stored.status == "pending"
    assert stored.email == "user@example.com"


def test_request_city_empty_input(client):
    response = client.post("/requests", json={"raw_input": ""})
    assert response.status_code == 422


def test_get_requests_page(client):
    create_response = client.post("/requests", json={"raw_input": "Portland Oregon", "email": "ops@example.com"})
    assert create_response.status_code == 201

    response = client.get("/requests")
    assert response.status_code == 200
    assert "Requested Cities" in response.text
    assert "Portland Oregon" in response.text
    assert "ops@example.com" in response.text
