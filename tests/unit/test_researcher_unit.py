import json
import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/groundwork_test")
os.environ.setdefault("PERPLEXITY_API_KEY", "test-pplx-key")
os.environ.setdefault("ADMIN_API_KEY", "test-key")

import app.researcher as researcher
from app.models import CityIntel

pytestmark = pytest.mark.unit


def test_generate_intel_retry_keeps_valid_role_alternation(monkeypatch):
    calls: list[list[dict[str, str]]] = []

    valid_payload = {
        "authorities": [{"name": "Transit Authority", "website": "https://example.com", "app": None}],
        "modes": [{"type": "metro", "operator": "Metro Co", "notes": "Frequent service"}],
        "payment_methods": [{"method": "Card", "details": "Tap to pay"}],
        "operating_hours": {"weekday": "5-23", "weekend": "6-23", "night_service": None},
        "rideshare": [{"provider": "Uber", "available": True, "notes": "Available"}],
        "airport_connections": [{"mode": "metro", "name": "Airport Line", "duration": "30 min", "cost": "$5"}],
        "delay_info": [{"source": "Status", "url": "https://example.com/status"}],
        "tips": "Use the metro for business districts.",
    }
    responses = ["not-json", json.dumps(valid_payload)]

    def fake_call(messages: list[dict[str, str]]) -> str:
        calls.append([dict(message) for message in messages])
        return responses[len(calls) - 1]

    monkeypatch.setattr(researcher, "_call_perplexity", fake_call)

    intel = researcher.generate_intel("Sydney", "Australia")
    assert intel.tips == "Use the metro for business districts."
    assert len(calls) == 2

    second_call_roles = [message["role"] for message in calls[1]]
    assert second_call_roles == ["system", "user", "assistant", "user"]
    assert calls[1][2]["content"] == "not-json"


def test_city_intel_accepts_light_rail_mode():
    payload = {
        "authorities": [{"name": "Transit Authority", "website": "https://example.com", "app": None}],
        "modes": [{"type": "light_rail", "operator": "Light Rail Co", "notes": "Frequent service"}],
        "payment_methods": [{"method": "Card", "details": "Tap to pay"}],
        "operating_hours": {"weekday": "5-23", "weekend": "6-23", "night_service": None},
        "rideshare": [{"provider": "Uber", "available": True, "notes": "Available"}],
        "airport_connections": [{"mode": "light_rail", "name": "Airport Link", "duration": "30 min", "cost": "$5"}],
        "delay_info": [{"source": "Status", "url": "https://example.com/status"}],
        "tips": "Use the light rail for business districts.",
    }

    intel = CityIntel.model_validate(payload)
    assert intel.modes[0].type == "light_rail"
