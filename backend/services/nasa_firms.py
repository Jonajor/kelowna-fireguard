"""
NASA FIRMS — Satellite fire hotspot detection.
Auth: Free API key — https://firms.modaps.eosdis.nasa.gov/api/area/
"""

import logging
from datetime import datetime

import httpx
from sqlalchemy import select, func

from core.config import settings
from core.database import async_session, NASAHotspot, Incident

logger = logging.getLogger(__name__)


async def collect_nasa_firms_data() -> dict:
    logger.info("[NASA FIRMS] Fetching satellite hotspots...")
    stats = {"fetched": 0, "stored": 0, "new_incidents": 0, "errors": []}

    if settings.NASA_FIRMS_KEY == "DEMO_KEY":
        logger.warning("[NASA FIRMS] Using DEMO_KEY — register for real key")

    try:
        area = f"{settings.BBOX_WEST},{settings.BBOX_SOUTH},{settings.BBOX_EAST},{settings.BBOX_NORTH}"
        url = f"{settings.NASA_FIRMS_CSV_URL}/{settings.NASA_FIRMS_KEY}/{settings.NASA_FIRMS_SOURCE}/{area}/2"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            logger.info("[NASA FIRMS] No hotspots detected")
            return stats

        headers = [h.strip() for h in lines[0].split(",")]
        stats["fetched"] = len(lines) - 1

        async with async_session() as session:
            for line in lines[1:]:
                values = [v.strip() for v in line.split(",")]
                if len(values) < len(headers):
                    continue
                row = dict(zip(headers, values))

                try:
                    lat = float(row.get("latitude", 0))
                    lng = float(row.get("longitude", 0))
                except ValueError:
                    continue
                if lat == 0 or lng == 0:
                    continue

                acq_date = row.get("acq_date", "")
                acq_time = row.get("acq_time", "")

                existing = await session.execute(
                    select(NASAHotspot).where(
                        NASAHotspot.latitude == lat,
                        NASAHotspot.longitude == lng,
                        NASAHotspot.acq_date == acq_date,
                        NASAHotspot.acq_time == acq_time,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                hotspot = NASAHotspot(
                    latitude=lat, longitude=lng,
                    brightness=_safe_float(row.get("bright_ti4")),
                    bright_ti5=_safe_float(row.get("bright_ti5")),
                    scan=_safe_float(row.get("scan")),
                    track=_safe_float(row.get("track")),
                    acq_date=acq_date, acq_time=acq_time,
                    satellite=row.get("satellite", ""),
                    instrument=row.get("instrument", ""),
                    confidence=row.get("confidence", "nominal"),
                    frp=_safe_float(row.get("frp")),
                    daynight=row.get("daynight", ""),
                )
                session.add(hotspot)
                stats["stored"] += 1

                near = await session.execute(
                    select(Incident).where(
                        Incident.is_active == True,
                        func.abs(Incident.latitude - lat) < 0.02,
                        func.abs(Incident.longitude - lng) < 0.02,
                    )
                )
                if not near.scalar_one_or_none():
                    conf_str = row.get("confidence", "nominal")
                    conf_val = {"high": 0.9, "nominal": 0.7, "low": 0.5}.get(conf_str, 0.7)
                    incident = Incident(
                        external_id=f"firms_{lat:.4f}_{lng:.4f}_{acq_date}_{acq_time}",
                        name=f"Satellite Detection ({acq_date} {acq_time})",
                        latitude=lat, longitude=lng,
                        status="monitoring",
                        threat_level="HIGH" if conf_str == "high" else "MODERATE",
                        source="NASA FIRMS", confidence=conf_val,
                    )
                    session.add(incident)
                    stats["new_incidents"] += 1

            await session.commit()

        logger.info(f"[NASA FIRMS] Done — {stats['stored']} stored, {stats['new_incidents']} new incidents")

    except Exception as e:
        stats["errors"].append(str(e)[:200])
        logger.error(f"[NASA FIRMS] Error: {e}", exc_info=True)

    return stats


def _safe_float(val, default=0.0):
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default
