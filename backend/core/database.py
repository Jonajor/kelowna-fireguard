"""
Database — async SQLAlchemy models.
SQLite for MVP, swap DATABASE_URL for PostgreSQL in production.
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Boolean, Text, Index,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(128), unique=True, nullable=True, index=True)
    name = Column(String(256), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String(32), default="active", index=True)
    threat_level = Column(String(16), default="MODERATE")
    size_hectares = Column(Float, default=0.0)
    containment_pct = Column(Float, default=0.0)
    source = Column(String(128))
    confidence = Column(Float, default=1.0)
    fire_cause = Column(String(128), nullable=True)
    fire_number = Column(String(32), nullable=True)
    geographic_desc = Column(String(512), nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)
    area = Column(String(256), nullable=False)
    message = Column(Text, nullable=False)
    source_count = Column(Integer, default=1)
    incident_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True)


class SocialPost(Base):
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(64), nullable=False)
    external_id = Column(String(256), nullable=True, unique=True)
    username = Column(String(128))
    text = Column(Text, nullable=False)
    url = Column(String(512), nullable=True)
    ai_fire_score = Column(Float, default=0.0, index=True)
    detected_keywords = Column(Text)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_text = Column(String(256), nullable=True)
    sentiment = Column(String(32), nullable=True)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)


class WeatherReading(Base):
    __tablename__ = "weather_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(64))
    source = Column(String(64), default="environment_canada")
    temperature_c = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    wind_speed_kmh = Column(Float, nullable=True)
    wind_gust_kmh = Column(Float, nullable=True)
    wind_direction = Column(String(8), nullable=True)
    wind_direction_deg = Column(Float, nullable=True)
    fire_weather_index = Column(Float, nullable=True)
    aqi = Column(Integer, nullable=True)
    visibility_km = Column(Float, nullable=True)
    uv_index = Column(Float, nullable=True)
    pressure_hpa = Column(Float, nullable=True)
    precipitation_mm = Column(Float, nullable=True)
    dew_point_c = Column(Float, nullable=True)
    condition_text = Column(String(256), nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)


class NASAHotspot(Base):
    __tablename__ = "nasa_hotspots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    brightness = Column(Float, nullable=True)
    bright_ti5 = Column(Float, nullable=True)
    scan = Column(Float, nullable=True)
    track = Column(Float, nullable=True)
    acq_date = Column(String(16), nullable=True)
    acq_time = Column(String(8), nullable=True)
    satellite = Column(String(16), nullable=True)
    instrument = Column(String(16), nullable=True)
    confidence = Column(String(8), nullable=True)
    frp = Column(Float, nullable=True)
    daynight = Column(String(1), nullable=True)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_hotspot_coords", "latitude", "longitude"),
    )


class EvacuationZone(Base):
    __tablename__ = "evacuation_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(128), unique=True, nullable=True, index=True)
    event_name = Column(String(256), nullable=False)
    event_number = Column(String(32), nullable=True)
    event_type = Column(String(64), nullable=True)
    order_alert_status = Column(String(32), nullable=False)
    issuing_agency = Column(String(256), nullable=True)
    homes_affected = Column(Integer, nullable=True)
    population_affected = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    event_start_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subreddit = Column(String(64), nullable=False)
    event_key = Column(String(256), nullable=False, unique=True, index=True)
    title = Column(String(512), nullable=False)
    body = Column(Text, nullable=False)
    reddit_post_id = Column(String(32), nullable=True)  # filled after successful post
    posted_at = Column(DateTime, default=datetime.utcnow, index=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
