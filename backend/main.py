"""
KelownaFireGuard — AI-Powered Wildfire Early Warning System
Backend API Server

Run: uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.database import init_db
from api.routes import router as api_router

from services.bc_wildfire import collect_bc_wildfire_data
from services.nasa_firms import collect_nasa_firms_data
from services.weather import collect_weather_data
from services.social_scanner import scan_social_media
from services.alert_engine import run_ai_analysis
from services.evacuation import collect_evacuation_data
from services.reddit_poster import run_reddit_poster

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("KelownaFireGuard starting up...")
    logger.info("=" * 60)

    await init_db()
    logger.info("Database initialized")

    scheduler.add_job(
        collect_bc_wildfire_data, "interval",
        seconds=settings.INTERVAL_BC_WILDFIRE, id="bc_wildfire",
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(
        collect_nasa_firms_data, "interval",
        seconds=settings.INTERVAL_NASA_FIRMS, id="nasa_firms",
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(
        collect_weather_data, "interval",
        seconds=settings.INTERVAL_WEATHER, id="weather",
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(
        scan_social_media, "interval",
        seconds=settings.INTERVAL_SOCIAL, id="social_scan",
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(
        collect_evacuation_data, "interval",
        seconds=settings.INTERVAL_EVACUATION, id="evacuation",
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(
        run_ai_analysis, "interval",
        seconds=settings.INTERVAL_AI_ANALYSIS, id="ai_analysis",
    )
    scheduler.add_job(
        run_reddit_poster, "interval",
        seconds=settings.INTERVAL_REDDIT_POSTER, id="reddit_poster",
    )

    scheduler.start()
    logger.info("Background collectors started")
    logger.info(f"API ready at http://localhost:8000/docs")
    logger.info(f"Monitoring: {settings.KELOWNA_LAT}°N, {abs(settings.KELOWNA_LNG)}°W, radius {settings.MONITORING_RADIUS_KM} km")
    logger.info("=" * 60)

    yield

    scheduler.shutdown()
    logger.info("KelownaFireGuard shut down")


app = FastAPI(
    title="KelownaFireGuard API",
    description="AI-Powered Wildfire Early Warning System for Kelowna, BC",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    jobs = {job.id: "running" for job in scheduler.get_jobs()}
    return {
        "status": "operational",
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "monitoring": {
            "center": f"{settings.KELOWNA_LAT}, {settings.KELOWNA_LNG}",
            "radius_km": settings.MONITORING_RADIUS_KM,
        },
        "collectors": jobs,
        "nasa_firms_key": "configured" if settings.NASA_FIRMS_KEY != "DEMO_KEY" else "DEMO_KEY",
        "openweather_key": "configured" if settings.OPENWEATHER_API_KEY else "not set",
        "reddit_poster": "configured" if settings.REDDIT_CLIENT_ID else "not configured",
    }
