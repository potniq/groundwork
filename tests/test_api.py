from sqlalchemy import select

from app.models import CityRequest


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
