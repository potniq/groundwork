from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, Float, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    city_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    metro_area_name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="generating")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    stale_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intel: Mapped[dict | None] = mapped_column(JSONB)
    raw_response: Mapped[str | None] = mapped_column(Text)


class CityRequest(Base):
    __tablename__ = "city_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")


class Authority(BaseModel):
    name: str
    website: str
    app: str | None = None


class TransportMode(BaseModel):
    type: Literal[
        "metro",
        "bus",
        "tram",
        "train",
        "ferry",
        "monorail",
        "cable_car",
        "funicular",
        "brt",
        "other",
    ]
    operator: str
    notes: str


class PaymentMethod(BaseModel):
    method: str
    details: str


class OperatingHours(BaseModel):
    weekday: str
    weekend: str
    night_service: str | None = None


class RideshareOption(BaseModel):
    provider: str
    available: bool
    notes: str


class AirportConnection(BaseModel):
    mode: str
    name: str
    duration: str
    cost: str


class DelaySource(BaseModel):
    source: str
    url: str


class CityIntel(BaseModel):
    authorities: list[Authority]
    modes: list[TransportMode]
    payment_methods: list[PaymentMethod]
    operating_hours: OperatingHours
    rideshare: list[RideshareOption]
    airport_connections: list[AirportConnection]
    delay_info: list[DelaySource]
    tips: str


class CityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    city_name: str
    country: str
    country_code: str
    latitude: float | None
    longitude: float | None
    status: str
    retrieved_at: datetime
    intel: CityIntel | None


class CityListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    city_name: str
    country: str
    country_code: str
    status: str


class CreateCityRequest(BaseModel):
    city_name: str
    country: str
    country_code: str
    latitude: float | None = None
    longitude: float | None = None
    slug: str | None = None


class CityRequestCreate(BaseModel):
    raw_input: str = Field(min_length=1)
    email: str | None = None

    @field_validator("raw_input")
    @classmethod
    def validate_raw_input(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("raw_input must not be empty")
        return cleaned
