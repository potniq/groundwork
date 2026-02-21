import os

import pytest
from pydantic import ValidationError

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/groundwork_test")
os.environ.setdefault("PERPLEXITY_API_KEY", "test-pplx-key")
os.environ.setdefault("ADMIN_API_KEY", "test-key")
os.environ.setdefault("VERIFY_GENERATED_URLS", "false")

from app.main import country_flag, slugify
from app.models import CityRequestCreate

pytestmark = pytest.mark.unit


def test_slugify_normalizes_ascii_and_delimiters():
    assert slugify("São Paulo, Brazil") == "sao-paulo-brazil"
    assert slugify("New   York!!!") == "new-york"


def test_country_flag_valid_and_invalid_codes():
    assert country_flag("US") == "🇺🇸"
    assert country_flag("gb") == "🇬🇧"
    assert country_flag("") == ""
    assert country_flag("USA") == ""
    assert country_flag("1A") == ""


def test_city_request_create_trims_input():
    request = CityRequestCreate(raw_input="   Joburg   ", email="ops@example.com")
    assert request.raw_input == "Joburg"
    assert request.email == "ops@example.com"


def test_city_request_create_rejects_blank_input():
    with pytest.raises(ValidationError):
        CityRequestCreate(raw_input="   ")
