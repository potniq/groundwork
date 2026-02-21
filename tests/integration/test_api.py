from datetime import UTC, datetime, timedelta

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


def _city_payload_for(city_name: str, country: str, country_code: str, latitude: float, longitude: float) -> dict:
    return {
        "city_name": city_name,
        "country": country,
        "country_code": country_code,
        "latitude": latitude,
        "longitude": longitude,
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


def test_get_cities_sorted_by_last_updated(client, db_session, sample_city):
    newer_city = City(
        slug="maribor-si",
        city_name="Maribor",
        country="Slovenia",
        country_code="SI",
        latitude=46.5547,
        longitude=15.6459,
        status="ready",
        intel=sample_city.intel,
        raw_response=sample_city.raw_response,
        retrieved_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    db_session.add(newer_city)
    db_session.commit()

    response = client.get("/cities")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["slug"] == "maribor-si"
    assert data[1]["slug"] == sample_city.slug


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
    assert ">iOS<" in response.text
    assert ">Android<" in response.text
    assert "Airport info" in response.text
    assert "Open" in response.text


def test_get_index_sorts_latest_first(client, db_session, sample_city):
    newer_city = City(
        slug="maribor-si",
        city_name="Maribor",
        country="Slovenia",
        country_code="SI",
        latitude=46.5547,
        longitude=15.6459,
        status="ready",
        intel=sample_city.intel,
        raw_response=sample_city.raw_response,
        retrieved_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    db_session.add(newer_city)
    db_session.commit()

    response = client.get("/")
    assert response.status_code == 200
    maribor_index = response.text.find("Maribor, Slovenia")
    barcelona_index = response.text.find("Barcelona, Spain")
    assert maribor_index != -1
    assert barcelona_index != -1
    assert maribor_index < barcelona_index


def test_get_city_html_hides_apps_without_store_links(client, db_session):
    city = City(
        slug="noapp-city-xx",
        city_name="NoApp City",
        country="Nowhere",
        country_code="XX",
        latitude=None,
        longitude=None,
        status="ready",
        intel={
            "authorities": [
                {
                    "name": "NoApp Transit",
                    "website": "https://example.com",
                    "apps": [
                        {
                            "name": "Ghost App",
                            "ios_url": None,
                            "android_url": None,
                        }
                    ],
                }
            ],
            "modes": [{"type": "bus", "operator": "NoApp Transit", "notes": "Daytime service"}],
            "payment_methods": [{"method": "Cash", "details": "Pay on board", "url": None}],
            "operating_hours": {"weekday": "06:00-22:00", "weekend": "08:00-20:00", "night_service": None},
            "rideshare": [{"provider": "N/A", "available": False, "notes": "Not available"}],
            "airport_connections": [
                {
                    "mode": "bus",
                    "name": "Airport Shuttle",
                    "duration": "25 min",
                    "cost": "EUR 4.00",
                    "info_url": "https://example.com/airport",
                }
            ],
            "delay_info": [{"source": "Status", "url": "https://example.com/status"}],
            "tips": "No app needed.",
        },
        raw_response="{}",
    )
    db_session.add(city)
    db_session.commit()

    response = client.get("/noapp-city-xx")
    assert response.status_code == 200
    assert "Ghost App" not in response.text
    assert ">iOS<" not in response.text
    assert ">Android<" not in response.text


def test_create_city_success(client, mock_perplexity_response):
    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=_city_payload())
    assert response.status_code == 201

    data = response.json()
    assert data["slug"] == "barcelona-es"
    assert data["status"] == "ready"
    assert data["intel"] is not None
    assert data["intel"]["authorities"]


@pytest.mark.parametrize(
    ("payload", "expected_slug"),
    [
        (_city_payload_for("Barcelona", "Spain", "ES", 41.3874, 2.1686), "barcelona-es"),
        (_city_payload_for("Milan", "Italy", "IT", 45.4642, 9.19), "milan-it"),
        (_city_payload_for("New York City", "United States", "US", 40.7128, -74.006), "new-york-city-us"),
        (_city_payload_for("London", "United Kingdom", "GB", 51.5072, -0.1276), "london-gb"),
        (_city_payload_for("Riga", "Latvia", "LV", 56.9496, 24.1052), "riga-lv"),
    ],
)
def test_create_city_success_for_fixture_city_payloads(client, mock_perplexity_response_by_city, payload, expected_slug):
    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["slug"] == expected_slug
    assert data["status"] == "ready"
    assert data["intel"] is not None
    assert data["intel"]["authorities"]


def test_create_city_custom_slug(client, mock_perplexity_response):
    payload = _city_payload()
    payload["slug"] = "barca-custom"

    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=payload)
    assert response.status_code == 201
    assert response.json()["slug"] == "barca-custom"


def test_create_city_regenerates_existing_slug(client, db_session, sample_city, mock_perplexity_response):
    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=_city_payload())
    assert response.status_code == 201

    data = response.json()
    assert data["slug"] == sample_city.slug
    assert data["status"] == "ready"
    assert data["intel"] is not None

    stored = db_session.scalar(select(City).where(City.slug == sample_city.slug))
    assert stored is not None
    assert stored.id == sample_city.id
    assert stored.status == "ready"


def test_create_city_conflict_when_generation_in_progress(client, db_session):
    city = City(
        slug="barcelona-es",
        city_name="Barcelona",
        country="Spain",
        country_code="ES",
        latitude=41.3874,
        longitude=2.1686,
        status="generating",
        intel=None,
        raw_response=None,
    )
    db_session.add(city)
    db_session.commit()

    response = client.post("/cities", headers={"X-API-Key": "test-key"}, json=_city_payload())
    assert response.status_code == 409
    assert response.json()["detail"] == "City is currently generating"


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
