import json
import logging
import re
import unicodedata
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
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
logger = logging.getLogger("groundwork.app")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((perf_counter() - start_time) * 1000, 2)
        logger.exception(
            "Unhandled request error",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms,
            },
        )
        raise

    duration_ms = round((perf_counter() - start_time) * 1000, 2)
    log_details = {
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }

    if response.status_code >= 500:
        logger.error("Request completed with server error", extra=log_details)
    elif response.status_code >= 400:
        logger.warning("Request completed with client error", extra=log_details)
    else:
        logger.info("Request completed", extra=log_details)

    return response


def template_context(request: Request, **context: object) -> dict[str, object]:
    settings = get_settings()
    hostname = (request.url.hostname or "").lower()
    posthog_debug = settings.POSTHOG_DEBUG or hostname in {"127.0.0.1", "localhost"}
    return {
        "request": request,
        "posthog_enabled": bool(settings.POSTHOG_PUBLIC_KEY),
        "posthog_public_key": settings.POSTHOG_PUBLIC_KEY,
        "posthog_host": settings.POSTHOG_HOST,
        "posthog_debug": posthog_debug,
        "posthog_capture_console_errors": settings.POSTHOG_CAPTURE_CONSOLE_ERRORS,
        "posthog_record_console_logs": settings.POSTHOG_RECORD_CONSOLE_LOGS,
        **context,
    }


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


def wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    return "text/html" in accept


def should_render_html_error_page(request: Request) -> bool:
    if request.method != "GET" or not wants_html(request):
        return False

    path = request.url.path
    if path.startswith("/static") or path.startswith("/cities") or path == "/health":
        return False

    return True


def render_error_page(
    request: Request,
    status_code: int,
    title: str,
    message: str,
    error_kind: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        template_context(
            request,
            status_code=status_code,
            error_title=title,
            error_message=message,
            analytics_context={
                "page_name": "error",
                "error_kind": error_kind,
                "status_code": status_code,
                "path": request.url.path,
            },
            analytics_super_properties={
                "current_page_name": "error",
            },
            analytics_reset_properties=[
                "current_city_slug",
                "current_city_name",
                "current_country",
            ],
        ),
        status_code=status_code,
    )


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
    if existing and existing.status == "generating":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="City is currently generating")

    if existing:
        city = existing
        city.city_name = payload.city_name
        city.country = payload.country
        city.country_code = payload.country_code.upper()
        city.latitude = payload.latitude
        city.longitude = payload.longitude
        city.metro_area_name = None
        city.status = "generating"
        city.intel = None
        city.raw_response = None
        city.stale_after = None
    else:
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


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    logger.warning(
        "HTTP exception raised",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": exc.status_code,
            "detail": str(exc.detail),
        },
    )

    if should_render_html_error_page(request):
        title = "Page not found" if exc.status_code == 404 else "Something went wrong"
        message = (
            "We could not find that page."
            if exc.status_code == 404
            else "The request could not be completed."
        )
        error_kind = "page_not_found" if exc.status_code == 404 else "http_error"
        return render_error_page(request, exc.status_code, title, message, error_kind)

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    logger.exception(
        "Unhandled application exception",
        extra={
            "method": request.method,
            "path": request.url.path,
        },
    )

    if should_render_html_error_page(request):
        return render_error_page(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Application error",
            message="Groundwork hit an unexpected error while loading this page.",
            error_kind="application_error",
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def get_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    cities = db.scalars(
        select(City)
        .where(City.status == "ready")
        .order_by(City.retrieved_at.desc(), City.city_name.asc())
    ).all()
    cards = [build_city_card(city) for city in cities]
    return templates.TemplateResponse(
        request,
        "index.html",
        template_context(
            request,
            cities=cards,
            analytics_context={
                "page_name": "home",
                "city_count": len(cards),
            },
            analytics_super_properties={
                "current_page_name": "home",
            },
            analytics_reset_properties=[
                "current_city_slug",
                "current_city_name",
                "current_country",
            ],
        ),
    )


@app.get("/cities", response_model=list[CityListItem])
def get_cities(db: Session = Depends(get_db)) -> list[CityListItem]:
    cities = db.scalars(
        select(City)
        .where(City.status == "ready")
        .order_by(City.retrieved_at.desc(), City.city_name.asc())
    ).all()
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


@app.get("/requests", response_class=HTMLResponse)
def get_requests_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    city_requests = db.scalars(
        select(CityRequest).order_by(CityRequest.requested_at.desc(), CityRequest.id.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "requests.html",
        template_context(
            request,
            city_requests=city_requests,
            analytics_context={
                "page_name": "requests",
                "request_count": len(city_requests),
            },
            analytics_super_properties={
                "current_page_name": "requests",
            },
            analytics_reset_properties=[
                "current_city_slug",
                "current_city_name",
                "current_country",
            ],
        ),
    )


@app.get("/{slug}", response_class=HTMLResponse)
def get_city_page(slug: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    city = db.scalar(select(City).where(City.slug == slug, City.status == "ready"))
    if not city:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City page not found")

    intel = CityIntel.model_validate(city.intel) if city.intel else None
    has_metro = bool(intel and any(mode.type == "metro" for mode in intel.modes))
    context = template_context(
        request,
        city=city,
        intel=intel,
        flag=country_flag(city.country_code),
        analytics_context={
            "page_name": "city_guide",
            "city_slug": city.slug,
            "city_name": city.city_name,
            "country": city.country,
            "authority_count": len(intel.authorities) if intel else 0,
            "mode_count": len(intel.modes) if intel else 0,
            "payment_method_count": len(intel.payment_methods) if intel else 0,
            "airport_connection_count": len(intel.airport_connections) if intel else 0,
            "has_metro": has_metro,
        },
        analytics_super_properties={
            "current_page_name": "city_guide",
            "current_city_slug": city.slug,
            "current_city_name": city.city_name,
            "current_country": city.country,
        },
    )
    return templates.TemplateResponse(request, "city.html", context)
