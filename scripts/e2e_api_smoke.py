#!/usr/bin/env python3
import json
import urllib.request

BASE_URL = "http://127.0.0.1:8080"
API_KEY = "test_key"


def request(path: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None):
    req_headers = dict(headers or {})
    data = None
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method, headers=req_headers)
    with urllib.request.urlopen(req, timeout=5) as response:
        body = response.read().decode("utf-8")
        content_type = response.headers.get("Content-Type", "")
        parsed_body = json.loads(body) if "application/json" in content_type else body
        return response.status, parsed_body


def main() -> None:
    status, health = request("/health")
    assert status == 200
    assert health == {"status": "ok"}

    status, cities = request("/cities")
    assert status == 200
    assert cities == []

    city_payload = {
        "city_name": "Barcelona",
        "country": "Spain",
        "country_code": "ES",
        "latitude": 41.3874,
        "longitude": 2.1686,
    }
    status, created_city = request(
        "/cities",
        method="POST",
        payload=city_payload,
        headers={"X-API-Key": API_KEY},
    )
    assert status == 201
    assert created_city["slug"] == "barcelona-es"
    assert created_city["status"] == "ready"
    assert created_city["intel"]["authorities"]

    status, cities = request("/cities")
    assert status == 200
    assert len(cities) == 1
    assert cities[0]["slug"] == "barcelona-es"

    status, city = request("/cities/barcelona-es")
    assert status == 200
    assert city["city_name"] == "Barcelona"
    assert city["intel"]["tips"]

    status, request_response = request(
        "/requests",
        method="POST",
        payload={"raw_input": "Lisbon Portugal", "email": "ops@example.com"},
    )
    assert status == 201
    assert "Thanks" in request_response["message"]

    status, requests_page = request("/requests")
    assert status == 200
    assert "Lisbon Portugal" in requests_page

    print("API E2E smoke tests passed.")


if __name__ == "__main__":
    main()
