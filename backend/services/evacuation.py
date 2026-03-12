"""
BC Evacuation Orders & Alerts Service
Source: BC Government ArcGIS REST API (public, no auth required)
"""

import logging
from datetime import datetime

import httpx
from sqlalchemy import select

from core.config import settings
from core.database import async_session, EvacuationZone

logger = logging.getLogger(__name__)


async def collect_evacuation_data() -> dict:
    logger.info("[Evacuation] Fetching evacuation orders and alerts...")
    stats = {"fetched": 0, "new": 0, "updated": 0, "cleared": 0, "errors": []}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "where": "1=1",
                "geometry": (
                    f'{{"xmin":{settings.BBOX_WEST},'
                    f'"ymin":{settings.BBOX_SOUTH},'
                    f'"xmax":{settings.BBOX_EAST},'
                    f'"ymax":{settings.BBOX_NORTH},'
                    f'"spatialReference":{{"wkid":4326}}}}'
                ),
                "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects",
                "inSR": "4326",
                "outFields": (
                    "OBJECTID,EVENT_NAME,EVENT_NUMBER,EVENT_TYPE,"
                    "ORDER_ALERT_STATUS,ISSUING_AGENCY,"
                    "EVENT_START_DATE,DATE_MODIFIED,"
                    "MULTI_SOURCED_HOMES,MULTI_SOURCED_POPULATION"
                ),
                "returnCentroid": "true",
                "outSR": "4326",
                "f": "json",
            }
            resp = await client.get(settings.BC_EVACUATION_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise ValueError(f"API error: {data['error']}")

        features = data.get("features", [])
        stats["fetched"] = len(features)
        active_ids = set()

        async with async_session() as session:
            for feat in features:
                attrs = feat.get("attributes", {})
                centroid = feat.get("centroid", {})

                obj_id = attrs.get("OBJECTID")
                if not obj_id:
                    continue

                external_id = f"evac_{obj_id}"
                active_ids.add(external_id)

                lat = centroid.get("y")
                lng = centroid.get("x")

                start_ts = attrs.get("EVENT_START_DATE")
                start_dt = datetime.utcfromtimestamp(start_ts / 1000) if start_ts else None

                result = await session.execute(
                    select(EvacuationZone).where(EvacuationZone.external_id == external_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.order_alert_status = attrs.get("ORDER_ALERT_STATUS", "")
                    existing.homes_affected = attrs.get("MULTI_SOURCED_HOMES")
                    existing.population_affected = attrs.get("MULTI_SOURCED_POPULATION")
                    existing.is_active = True
                    existing.collected_at = datetime.utcnow()
                    stats["updated"] += 1
                else:
                    zone = EvacuationZone(
                        external_id=external_id,
                        event_name=attrs.get("EVENT_NAME", "Unknown"),
                        event_number=attrs.get("EVENT_NUMBER"),
                        event_type=attrs.get("EVENT_TYPE", "Wildfire"),
                        order_alert_status=attrs.get("ORDER_ALERT_STATUS", "Alert"),
                        issuing_agency=attrs.get("ISSUING_AGENCY"),
                        homes_affected=attrs.get("MULTI_SOURCED_HOMES"),
                        population_affected=attrs.get("MULTI_SOURCED_POPULATION"),
                        latitude=lat,
                        longitude=lng,
                        event_start_date=start_dt,
                    )
                    session.add(zone)
                    stats["new"] += 1

            # Mark zones no longer in the API response as inactive
            all_zones = (await session.execute(
                select(EvacuationZone).where(EvacuationZone.is_active == True)
            )).scalars().all()
            for zone in all_zones:
                if zone.external_id not in active_ids:
                    zone.is_active = False
                    stats["cleared"] += 1

            await session.commit()

        logger.info(f"[Evacuation] Done — {stats['new']} new, {stats['updated']} updated, {stats['cleared']} cleared")

    except Exception as e:
        stats["errors"].append(str(e)[:200])
        logger.error(f"[Evacuation] Error: {e}", exc_info=True)

    return stats
