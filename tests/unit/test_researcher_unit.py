import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/groundwork_test")
os.environ.setdefault("PERPLEXITY_API_KEY", "test-pplx-key")
os.environ.setdefault("ADMIN_API_KEY", "test-key")
os.environ.setdefault("VERIFY_GENERATED_URLS", "false")

import app.researcher as researcher
from app.models import CityIntel

pytestmark = pytest.mark.unit


def test_generate_intel_retry_keeps_valid_role_alternation(monkeypatch):
    calls: list[list[dict[str, str]]] = []

    valid_payload = {
        "authorities": [
            {
                "name": "Transit Authority",
                "website": "https://example.com",
                "apps": [
                    {
                        "name": "Transit App",
                        "ios_url": "https://apps.apple.com/app/transit-app/id123456",
                        "android_url": "https://play.google.com/store/apps/details?id=com.example.transit",
                    }
                ],
            }
        ],
        "modes": [{"type": "metro", "operator": "Metro Co", "notes": "Frequent service"}],
        "payment_methods": [{"method": "Card", "details": "Tap to pay", "url": None}],
        "operating_hours": {"weekday": "5-23", "weekend": "6-23", "night_service": None},
        "rideshare": [{"provider": "Uber", "available": True, "notes": "Available"}],
        "airport_connections": [
            {
                "mode": "metro",
                "name": "Airport Line",
                "duration": "30 min",
                "cost": "$5",
                "info_url": "https://example.com/airport-line",
            }
        ],
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
        "authorities": [{"name": "Transit Authority", "website": "https://example.com", "apps": []}],
        "modes": [{"type": "light_rail", "operator": "Light Rail Co", "notes": "Frequent service"}],
        "payment_methods": [{"method": "Card", "details": "Tap to pay", "url": None}],
        "operating_hours": {"weekday": "5-23", "weekend": "6-23", "night_service": None},
        "rideshare": [{"provider": "Uber", "available": True, "notes": "Available"}],
        "airport_connections": [
            {
                "mode": "light_rail",
                "name": "Airport Link",
                "duration": "30 min",
                "cost": "$5",
                "info_url": "https://example.com/airport-link",
            }
        ],
        "delay_info": [{"source": "Status", "url": "https://example.com/status"}],
        "tips": "Use the light rail for business districts.",
    }

    intel = CityIntel.model_validate(payload)
    assert intel.modes[0].type == "light_rail"


def test_generate_intel_retries_when_url_validation_fails(monkeypatch):
    calls: list[list[dict[str, str]]] = []

    bad_payload = {
        "authorities": [{"name": "Transit Authority", "website": "https://invalid.example", "apps": []}],
        "modes": [{"type": "metro", "operator": "Metro Co", "notes": "Frequent service"}],
        "payment_methods": [{"method": "Card", "details": "Tap to pay", "url": None}],
        "operating_hours": {"weekday": "5-23", "weekend": "6-23", "night_service": None},
        "rideshare": [{"provider": "Uber", "available": True, "notes": "Available"}],
        "airport_connections": [{"mode": "metro", "name": "Airport Line", "duration": "30 min", "cost": "$5", "info_url": None}],
        "delay_info": [{"source": "Status", "url": "https://invalid.example/status"}],
        "tips": "First pass.",
    }
    good_payload = {
        "authorities": [{"name": "Transit Authority", "website": "https://t.example.com", "apps": []}],
        "modes": [{"type": "metro", "operator": "Metro Co", "notes": "Frequent service"}],
        "payment_methods": [{"method": "Card", "details": "Tap to pay", "url": None}],
        "operating_hours": {"weekday": "5-23", "weekend": "6-23", "night_service": None},
        "rideshare": [{"provider": "Uber", "available": True, "notes": "Available"}],
        "airport_connections": [{"mode": "metro", "name": "Airport Line", "duration": "30 min", "cost": "$5", "info_url": None}],
        "delay_info": [{"source": "Status", "url": "https://t.example.com/status"}],
        "tips": "Second pass.",
    }

    responses = [json.dumps(bad_payload), json.dumps(good_payload)]

    monkeypatch.setenv("VERIFY_GENERATED_URLS", "true")
    researcher.get_settings.cache_clear()

    def fake_call(messages: list[dict[str, str]]) -> str:
        calls.append([dict(message) for message in messages])
        return responses[len(calls) - 1]

    def fake_validate_urls(intel: CityIntel, timeout_seconds: float) -> dict[str, str]:
        if intel.tips == "First pass.":
            return {"https://invalid.example": "HTTP 404"}
        return {}

    monkeypatch.setattr(researcher, "_call_perplexity", fake_call)
    monkeypatch.setattr(researcher, "_validate_intel_urls", fake_validate_urls)

    intel = researcher.generate_intel("Sydney", "Australia")
    assert intel.tips == "Second pass."
    assert len(calls) == 2

    second_call_roles = [message["role"] for message in calls[1]]
    assert second_call_roles == ["system", "user", "assistant", "user"]
    assert "invalid or unreachable URLs" in calls[1][3]["content"]

    researcher.get_settings.cache_clear()


def test_generate_intel_reads_mock_file(monkeypatch, tmp_path: Path):
    payload = {
        "authorities": [{"name": "Transit Authority", "website": "https://example.com", "apps": []}],
        "modes": [{"type": "metro", "operator": "Metro Co", "notes": "Frequent service"}],
        "payment_methods": [{"method": "Card", "details": "Tap to pay", "url": None}],
        "operating_hours": {"weekday": "5-23", "weekend": "6-23", "night_service": None},
        "rideshare": [{"provider": "Uber", "available": True, "notes": "Available"}],
        "airport_connections": [
            {
                "mode": "metro",
                "name": "Airport Line",
                "duration": "30 min",
                "cost": "$5",
                "info_url": "https://example.com/airport-line",
            }
        ],
        "delay_info": [{"source": "Status", "url": "https://example.com/status"}],
        "tips": "Fixture intel.",
    }
    fixture_file = tmp_path / "intel.json"
    fixture_file.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("PERPLEXITY_MOCK_RESPONSE_FILE", str(fixture_file))
    researcher.get_settings.cache_clear()

    def fail_call(_: list[dict[str, str]]) -> str:
        raise AssertionError("Perplexity API should not be called when mock fixture is configured")

    monkeypatch.setattr(researcher, "_call_perplexity", fail_call)

    intel = researcher.generate_intel("Sydney", "Australia")
    assert intel.tips == "Fixture intel."

    researcher.get_settings.cache_clear()


def test_system_prompt_includes_link_requirements():
    prompt = researcher._system_prompt()
    assert '"ios_url":"string|null"' in prompt
    assert '"android_url":"string|null"' in prompt
    assert '"url":"string|null"' in prompt
    assert '"info_url":"string|null"' in prompt
    assert "official URL in payment_methods.url" in prompt
    assert "airport_connections.info_url" in prompt
    assert "Assume the traveler needs English output" in prompt
    assert "prefer official English-language pages" in prompt
    assert "English variant with a '-en' path suffix" in prompt
    assert "If no English page exists, use the official non-English page" in prompt
    assert "verify each non-null URL is reachable" in prompt
    assert "verifiable, cited sources" in prompt
