"""
Alert Engine — Multi-source AI risk scoring (0-100).
Components: Active fires (0-25) + Satellite (0-25) + Weather (0-25) + Social (0-25)
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, desc

from core.config import settings
from core.database import (
    async_session, Incident, Alert, SocialPost,
    WeatherReading, NASAHotspot,
)

logger = logging.getLogger(__name__)


async def run_ai_analysis() -> dict:
    logger.info("[AI] Running multi-source analysis...")
    stats = {"risk_score": 0, "factors": [], "alert_created": False}

    try:
        async with async_session() as session:
            cutoff = datetime.utcnow() - timedelta(hours=1)

            inc_result = await session.execute(
                select(Incident).where(Incident.is_active == True, Incident.status == "active")
            )
            active_incidents = inc_result.scalars().all()

            social_count = (await session.execute(
                select(func.count(SocialPost.id)).where(
                    SocialPost.collected_at >= cutoff,
                    SocialPost.ai_fire_score >= settings.AI_DETECTION_THRESHOLD,
                )
            )).scalar() or 0

            hotspot_count = (await session.execute(
                select(func.count(NASAHotspot.id)).where(NASAHotspot.collected_at >= cutoff)
            )).scalar() or 0

            weather = (await session.execute(
                select(WeatherReading).order_by(desc(WeatherReading.recorded_at)).limit(1)
            )).scalar_one_or_none()

            # Score components
            fire_pts, fire_f = _score_fires(active_incidents)
            sat_pts, sat_f = _score_satellite(hotspot_count)
            wx_pts, wx_f = _score_weather(weather)
            soc_pts, soc_f = _score_social(social_count)

            # Cross-reference bonus
            source_count = sum([fire_pts > 0, sat_pts > 0, soc_pts > 5])
            cross_ref = 10 if source_count >= 3 else 5 if source_count >= 2 else 0

            total = min(100, fire_pts + sat_pts + wx_pts + soc_pts + cross_ref)
            all_factors = fire_f + sat_f + wx_f + soc_f
            if cross_ref:
                all_factors.append(f"Multi-source confirmation ({source_count} sources)")

            stats.update({"risk_score": total, "factors": all_factors})

            if total >= 60:
                severity = "CRITICAL" if total >= 85 else "HIGH"
                alert = Alert(
                    alert_type="ai_detection", severity=severity,
                    area="Central Okanagan — Kelowna Region",
                    message=(
                        f"AI Threat Assessment: Risk Score {total}/100 ({severity}). "
                        f"{len(active_incidents)} active fires, {hotspot_count} satellite hotspots, "
                        f"{social_count} social signals. Factors: {'; '.join(all_factors[:5])}."
                    ),
                    source_count=len(active_incidents) + hotspot_count + social_count,
                )
                session.add(alert)
                await session.commit()
                stats["alert_created"] = True

            logger.info(f"[AI] Risk: {total}/100 — Fire:{fire_pts} Sat:{sat_pts} Wx:{wx_pts} Soc:{soc_pts}")

    except Exception as e:
        logger.error(f"[AI] Error: {e}", exc_info=True)

    return stats


def _score_fires(incidents):
    if not incidents: return 0, []
    score, factors = 0, []
    critical = sum(1 for i in incidents if i.threat_level == "CRITICAL")
    high = sum(1 for i in incidents if i.threat_level == "HIGH")
    total_ha = sum(i.size_hectares or 0 for i in incidents)
    if critical: score += 15; factors.append(f"{critical} CRITICAL fire(s)")
    if high: score += 8; factors.append(f"{high} HIGH fire(s)")
    elif incidents: score += 5
    if total_ha > 500: score += 5; factors.append(f"Total: {total_ha:.0f} ha")
    return min(score, 25), factors


def _score_satellite(count):
    if not count: return 0, []
    f = [f"{count} satellite hotspot(s)"]
    if count > 10: return 25, f
    if count > 5: return 18, f
    if count > 2: return 12, f
    return 7, f


def _score_weather(w):
    if not w: return 0, []
    score, factors = 0, []
    if w.temperature_c and w.temperature_c >= settings.TEMP_ALERT_C:
        score += 8; factors.append(f"Temp: {w.temperature_c:.1f}°C")
    if w.humidity_pct and w.humidity_pct <= settings.HUMIDITY_ALERT_PCT:
        score += 8; factors.append(f"Humidity: {w.humidity_pct:.0f}%")
    if w.wind_speed_kmh and w.wind_speed_kmh >= settings.WIND_ALERT_KMH:
        score += 7; factors.append(f"Wind: {w.wind_speed_kmh:.0f} km/h")
    if w.fire_weather_index and w.fire_weather_index >= settings.FWI_EXTREME:
        score += 5; factors.append(f"FWI: {w.fire_weather_index:.1f}")
    return min(score, 25), factors


def _score_social(count):
    if not count: return 0, []
    f = [f"{count} fire-related post(s)"]
    if count > 20: return 25, f
    if count > 10: return 18, f
    if count > 5: return 12, f
    return 5, f
