"""
BC Wildfire Service — Real-time active fire data.
Source: BC Government ArcGIS REST API (public, no auth required)
"""

import logging
from datetime import datetime

import httpx
from sqlalchemy import select

from core.config import settings
from core.database import async_session, Incident

logger = logging.getLogger(__name__)


async def collect_bc_wildfire_data() -> dict:
    logger.info("[BC Wildfire] Fetching active fires...")
    stats = {"fetched": 0, "new": 0, "updated": 0, "errors": []}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "where": "FIRE_STATUS <> 'Out'",
                "geometry": (
                    f'{{"xmin":{settings.BBOX_WEST},'
                    f'"ymin":{settings.BBOX_SOUTH},'
                    f'"xmax":{settings.BBOX_EAST},'
                    f'"ymax":{settings.BBOX_NORTH},'
                    f'"spatialReference":{{"wkid":4326}}}}'
                ),
                "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": (
                    "FIRE_NUMBER,FIRE_YEAR,FIRE_CAUSE,"
                    "FIRE_STATUS,CURRENT_SIZE,"
                    "GEOGRAPHIC_DESCRIPTION,LATITUDE,LONGITUDE,"
                    "FIRE_URL,IGNITION_DATE,FIRE_OF_NOTE_IND,OBJECTID"
                ),
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "json",
            }
            resp = await client.get(settings.BC_WILDFIRE_ACTIVE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        features = data.get("features", [])
        stats["fetched"] = len(features)
        logger.info(f"[BC Wildfire] Received {len(features)} fires in region")

        async with async_session() as session:
            for feat in features:
                attrs = feat.get("attributes", {})
                geom = feat.get("geometry", {})

                fire_number = attrs.get("FIRE_NUMBER", "")
                if not fire_number:
                    continue

                external_id = f"bcws_{fire_number}"
                size_ha = attrs.get("CURRENT_SIZE") or 0
                status_raw = (attrs.get("FIRE_STATUS") or "Active").strip()
                geographic_desc = attrs.get("GEOGRAPHIC_DESCRIPTION") or "Unknown"

                lat = geom.get("y") or attrs.get("LATITUDE") or 0
                lng = geom.get("x") or attrs.get("LONGITUDE") or 0
                if lat == 0 or lng == 0:
                    continue

                status = _map_status(status_raw)
                threat = _assess_threat(size_ha, status, attrs.get("FIRE_OF_NOTE_IND"))

                result = await session.execute(
                    select(Incident).where(Incident.external_id == external_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.size_hectares = size_ha
                    existing.status = status
                    existing.threat_level = threat
                    existing.geographic_desc = geographic_desc
                    existing.updated_at = datetime.utcnow()
                    stats["updated"] += 1
                else:
                    name = geographic_desc if geographic_desc != "Unknown" else f"Fire {fire_number}"
                    incident = Incident(
                        external_id=external_id, name=name,
                        latitude=lat, longitude=lng,
                        status=status, threat_level=threat,
                        size_hectares=size_ha,
                        containment_pct=_estimate_containment(status),
                        source="BC Wildfire Service", confidence=1.0,
                        fire_cause=attrs.get("FIRE_CAUSE"),
                        fire_number=fire_number,
                        geographic_desc=geographic_desc,
                    )
                    session.add(incident)
                    stats["new"] += 1

            await session.commit()

        logger.info(f"[BC Wildfire] Done — {stats['new']} new, {stats['updated']} updated")

    except Exception as e:
        stats["errors"].append(str(e)[:200])
        logger.error(f"[BC Wildfire] Error: {e}", exc_info=True)

    return stats


def _map_status(raw: str) -> str:
    return {
        "Out of Control": "active", "Active": "active",
        "Being Held": "monitoring", "Under Control": "contained",
        "Out": "contained", "New": "active",
    }.get(raw, "monitoring")


def _assess_threat(size_ha, status, fire_of_note=None) -> str:
    if fire_of_note == "Y":
        return "CRITICAL"
    if status == "active":
        if size_ha > 100: return "CRITICAL"
        if size_ha > 10: return "HIGH"
        return "MODERATE"
    if status == "monitoring":
        return "MODERATE" if size_ha > 5 else "LOW"
    return "LOW"


def _estimate_containment(status: str) -> float:
    return {"active": 10.0, "monitoring": 60.0, "contained": 90.0}.get(status, 50.0)
