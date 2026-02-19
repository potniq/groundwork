import json
import re
import unicodedata
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import City, CityIntel, CityListItem, CityRequest, CityRequestCreate, CityResponse, CreateCityRequest
from app.researcher import generate_intel


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="Groundwork by Potniq", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug


def country_flag(country_code: str) -> str:
    code = (country_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(127397 + ord(char)) for char in code)


def to_city_response(city: City) -> CityResponse:
    intel = CityIntel.model_validate(city.intel) if city.intel else None
    return CityResponse(
        slug=city.slug,
        city_name=city.city_name,
        country=city.country,
        country_code=city.country_code,
        latitude=city.latitude,
        longitude=city.longitude,
        status=city.status,
        retrieved_at=city.retrieved_at,
        intel=intel,
    )


def to_city_list_item(city: City) -> CityListItem:
    return CityListItem(
        slug=city.slug,
        city_name=city.city_name,
        country=city.country,
        country_code=city.country_code,
        status=city.status,
    )


def build_city_card(city: City) -> dict[str, str | bool]:
    intel = CityIntel.model_validate(city.intel) if city.intel else None
    has_metro = bool(intel and any(mode.type == "metro" for mode in intel.modes))
    contactless = bool(
        intel
        and any(
            "contactless" in f"{method.method} {method.details}".lower() for method in intel.payment_methods
        )
    )
    rideshare = []
    if intel:
        rideshare = [option.provider for option in intel.rideshare if option.available]

    return {
        "slug": city.slug,
        "city_name": city.city_name,
        "country": city.country,
        "country_code": city.country_code,
        "flag": country_flag(city.country_code),
        "has_metro": has_metro,
        "contactless": contactless,
        "rideshare": ", ".join(rideshare) if rideshare else "None listed",
    }


def create_city_profile(db: Session, payload: CreateCityRequest) -> City:
    generated_slug = slugify(f"{payload.city_name}-{payload.country_code}")
    slug = (payload.slug or generated_slug).strip()
    if not slug:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slug cannot be empty")

    existing = db.scalar(select(City).where(City.slug == slug))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="City already exists")

    city = City(
        slug=slug,
        city_name=payload.city_name,
        country=payload.country,
        country_code=payload.country_code.upper(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        metro_area_name=None,
        status="generating",
    )
    db.add(city)
    db.commit()
    db.refresh(city)

    try:
        intel = generate_intel(city.city_name, city.country)
        city.status = "ready"
        city.intel = intel.model_dump()
        city.raw_response = json.dumps(city.intel)
        city.retrieved_at = datetime.now(UTC)
        city.stale_after = city.retrieved_at + timedelta(days=30)
    except Exception as exc:  # noqa: BLE001
        city.status = "failed"
        db.commit()
        db.refresh(city)
        raise RuntimeError(str(exc)) from exc

    db.commit()
    db.refresh(city)
    return city


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def get_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    cities = db.scalars(select(City).where(City.status == "ready").order_by(City.city_name.asc())).all()
    cards = [build_city_card(city) for city in cities]
    return templates.TemplateResponse("index.html", {"request": request, "cities": cards})


@app.get("/cities", response_model=list[CityListItem])
def get_cities(db: Session = Depends(get_db)) -> list[CityListItem]:
    cities = db.scalars(select(City).where(City.status == "ready").order_by(City.city_name.asc())).all()
    return [to_city_list_item(city) for city in cities]


@app.get("/cities/{slug}", response_model=CityResponse)
def get_city(slug: str, db: Session = Depends(get_db)) -> CityResponse:
    city = db.scalar(select(City).where(City.slug == slug))
    if not city:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")
    return to_city_response(city)


@app.post("/cities", response_model=CityResponse, status_code=status.HTTP_201_CREATED)
def create_city(
    payload: CreateCityRequest,
    db: Session = Depends(get_db),
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> CityResponse:
    settings = get_settings()
    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

    try:
        city = create_city_profile(db, payload)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"City generation failed: {exc}") from exc

    return to_city_response(city)


@app.post("/requests", status_code=status.HTTP_201_CREATED)
def request_city(payload: CityRequestCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    city_request = CityRequest(raw_input=payload.raw_input, email=payload.email, status="pending")
    db.add(city_request)
    db.commit()
    return {"message": "Thanks, we received your city request."}


@app.get("/{slug}", response_class=HTMLResponse)
def get_city_page(slug: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    city = db.scalar(select(City).where(City.slug == slug, City.status == "ready"))
    if not city:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City page not found")

    intel = CityIntel.model_validate(city.intel) if city.intel else None
    context = {
        "request": request,
        "city": city,
        "intel": intel,
        "flag": country_flag(city.country_code),
    }
    return templates.TemplateResponse("city.html", context)
