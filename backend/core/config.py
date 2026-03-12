"""
Configuration — all API endpoints, thresholds, and settings.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

# .env lives at the project root, one level above backend/
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "KelownaFireGuard"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./fireguard.db")

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:4173",
        "https://kelownafireguard.ca",
    ]

    KELOWNA_LAT: float = float(os.getenv("KELOWNA_LAT", "49.8880"))
    KELOWNA_LNG: float = float(os.getenv("KELOWNA_LNG", "-119.4960"))
    MONITORING_RADIUS_KM: float = float(os.getenv("MONITORING_RADIUS_KM", "50"))
    BBOX_NORTH: float = float(os.getenv("BBOX_NORTH", "50.15"))
    BBOX_SOUTH: float = float(os.getenv("BBOX_SOUTH", "49.60"))
    BBOX_WEST: float = float(os.getenv("BBOX_WEST", "-119.90"))
    BBOX_EAST: float = float(os.getenv("BBOX_EAST", "-119.10"))

    # BC Evacuation Orders & Alerts — Public ArcGIS REST (NO auth)
    BC_EVACUATION_URL: str = (
        "https://services6.arcgis.com/ubm4tcTYICKBpist/"
        "arcgis/rest/services/Evacuation_Orders_and_Alerts/"
        "FeatureServer/0/query"
    )
    INTERVAL_EVACUATION: int = 300

    # BC Wildfire Service — Public ArcGIS REST (NO auth)
    BC_WILDFIRE_ACTIVE_URL: str = (
        "https://services6.arcgis.com/ubm4tcTYICKBpist/"
        "arcgis/rest/services/BCWS_ActiveFires_PublicView/"
        "FeatureServer/0/query"
    )
    BC_WILDFIRE_PERIMETERS_URL: str = (
        "https://services6.arcgis.com/ubm4tcTYICKBpist/"
        "arcgis/rest/services/BCWS_FirePerimeters_PublicView/"
        "FeatureServer/0/query"
    )

    # NASA FIRMS — free API key: https://firms.modaps.eosdis.nasa.gov/api/area/
    NASA_FIRMS_KEY: str = os.getenv("NASA_FIRMS_KEY", "DEMO_KEY")
    NASA_FIRMS_CSV_URL: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    NASA_FIRMS_SOURCE: str = "VIIRS_SNPP_NRT"

    # Environment Canada — Public (NO auth)
    EC_STATION_ID: str = "CXKL"
    EC_FORECAST_CITY_URL: str = (
        "https://dd.weather.gc.ca/citypage_weather/xml/BC/s0000568_e.xml"
    )

    # OpenWeatherMap — optional, free tier 1000/day
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    OPENWEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5"
    OPENWEATHER_AQI_URL: str = "https://api.openweathermap.org/data/2.5/air_pollution"

    # Reddit — public JSON, no auth for read-only
    REDDIT_USER_AGENT: str = "KelownaFireGuard/1.0 (fire monitoring bot)"
    REDDIT_SUBREDDITS: list[str] = ["kelowna", "britishcolumbia", "okanagan"]

    # RSS News Feeds
    NEWS_FEEDS: list[dict] = [
        {"name": "Castanet Kelowna", "url": "https://www.castanet.net/rss/kelowna.xml"},
        {"name": "CBC British Columbia", "url": "https://www.cbc.ca/webfeed/rss/rss-canada-britishcolumbia"},
        {"name": "Global News Okanagan", "url": "https://globalnews.ca/okanagan/feed/"},
        {"name": "InfoNews Penticton", "url": "https://www.infonews.ca/feed/"},
    ]

    AI_DETECTION_THRESHOLD: float = float(os.getenv("AI_DETECTION_THRESHOLD", "0.75"))
    SOCIAL_SPIKE_THRESHOLD: int = int(os.getenv("SOCIAL_SPIKE_THRESHOLD", "5"))

    TEMP_ALERT_C: float = float(os.getenv("TEMP_ALERT_C", "35.0"))
    HUMIDITY_ALERT_PCT: float = float(os.getenv("HUMIDITY_ALERT_PCT", "15.0"))
    WIND_ALERT_KMH: float = float(os.getenv("WIND_ALERT_KMH", "40.0"))
    FWI_EXTREME: float = 25.0

    # Scheduler intervals (seconds)
    INTERVAL_BC_WILDFIRE: int = 300
    INTERVAL_NASA_FIRMS: int = 600
    INTERVAL_WEATHER: int = 900
    INTERVAL_SOCIAL: int = 120
    INTERVAL_AI_ANALYSIS: int = 300

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
