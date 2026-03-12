"""
API Routes — REST endpoints + WebSocket.
All data from database, populated by background collectors.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import (
    APIRouter, Depends, WebSocket, WebSocketDisconnect,
    Query, HTTPException,
)
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import (
    get_session, Incident, Alert, SocialPost,
    WeatherReading, NASAHotspot, EvacuationZone,
)
from services.nlp_engine import NLPEngine
from api.websocket import manager

logger = logging.getLogger(__name__)
router = APIRouter()
nlp = NLPEngine()


@router.get("/incidents")
async def get_incidents(
    status: Optional[str] = None, threat_level: Optional[str] = None,
    source: Optional[str] = None, limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = select(Incident).where(Incident.is_active == True)
    if status: query = query.where(Incident.status == status)
    if threat_level: query = query.where(Incident.threat_level == threat_level)
    if source: query = query.where(Incident.source.ilike(f"%{source}%"))
    query = query.order_by(desc(Incident.updated_at)).limit(limit)
    result = await session.execute(query)
    incidents = result.scalars().all()
    return {"count": len(incidents), "updated_at": datetime.utcnow().isoformat(),
            "incidents": [_ser_incident(i) for i in incidents]}


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident: raise HTTPException(404, "Not found")
    return _ser_incident(incident)


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None, alert_type: Optional[str] = None,
    hours: int = Query(24, le=168), active_only: bool = True,
    limit: int = Query(50, le=200), session: AsyncSession = Depends(get_session),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = select(Alert).where(Alert.created_at >= cutoff)
    if active_only: query = query.where(Alert.is_active == True)
    if severity: query = query.where(Alert.severity == severity)
    if alert_type: query = query.where(Alert.alert_type == alert_type)
    query = query.order_by(desc(Alert.created_at)).limit(limit)
    result = await session.execute(query)
    alerts = result.scalars().all()
    return {"count": len(alerts), "alerts": [
        {"id": a.id, "type": a.alert_type, "severity": a.severity, "area": a.area,
         "message": a.message, "source_count": a.source_count,
         "acknowledged": a.acknowledged, "created_at": a.created_at.isoformat()}
        for a in alerts
    ]}


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert: raise HTTPException(404, "Not found")
    alert.acknowledged = True
    await session.commit()
    return {"id": alert_id, "acknowledged": True}


@router.get("/social")
async def get_social_feed(
    min_score: float = Query(0.5, ge=0, le=1), platform: Optional[str] = None,
    hours: int = Query(12, le=72), limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = select(SocialPost).where(
        SocialPost.collected_at >= cutoff, SocialPost.ai_fire_score >= min_score,
    )
    if platform: query = query.where(SocialPost.platform.ilike(f"%{platform}%"))
    query = query.order_by(desc(SocialPost.ai_fire_score)).limit(limit)
    result = await session.execute(query)
    posts = result.scalars().all()
    return {"count": len(posts), "posts": [
        {"id": p.id, "platform": p.platform, "username": p.username,
         "text": p.text, "url": p.url, "ai_score": p.ai_fire_score,
         "keywords": json.loads(p.detected_keywords) if p.detected_keywords else [],
         "location": p.location_text, "sentiment": p.sentiment,
         "collected_at": p.collected_at.isoformat()}
        for p in posts
    ]}


@router.get("/weather")
async def get_weather(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(WeatherReading).order_by(desc(WeatherReading.recorded_at)).limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        return {"available": False, "message": "No weather data yet. Collectors start within 15 min."}
    fwi = r.fire_weather_index
    return {
        "available": True, "source": r.source,
        "temperature_c": r.temperature_c, "humidity_pct": r.humidity_pct,
        "wind_speed_kmh": r.wind_speed_kmh, "wind_gust_kmh": r.wind_gust_kmh,
        "wind_direction": r.wind_direction, "fire_weather_index": fwi,
        "fire_weather_rating": _fwi_rating(fwi),
        "aqi": r.aqi, "uv_index": r.uv_index, "visibility_km": r.visibility_km,
        "pressure_hpa": r.pressure_hpa, "condition": r.condition_text,
        "recorded_at": r.recorded_at.isoformat(),
    }


@router.get("/weather/history")
async def get_weather_history(hours: int = Query(24, le=168), session: AsyncSession = Depends(get_session)):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    result = await session.execute(
        select(WeatherReading).where(WeatherReading.recorded_at >= cutoff).order_by(WeatherReading.recorded_at)
    )
    readings = result.scalars().all()
    return {"count": len(readings), "readings": [
        {"temperature_c": r.temperature_c, "humidity_pct": r.humidity_pct,
         "wind_speed_kmh": r.wind_speed_kmh, "fwi": r.fire_weather_index,
         "aqi": r.aqi, "recorded_at": r.recorded_at.isoformat()}
        for r in readings
    ]}


@router.get("/hotspots")
async def get_hotspots(
    hours: int = Query(48, le=168), confidence: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = select(NASAHotspot).where(NASAHotspot.collected_at >= cutoff)
    if confidence: query = query.where(NASAHotspot.confidence == confidence)
    query = query.order_by(desc(NASAHotspot.collected_at))
    result = await session.execute(query)
    hotspots = result.scalars().all()
    return {"count": len(hotspots), "hotspots": [
        {"latitude": h.latitude, "longitude": h.longitude, "brightness": h.brightness,
         "confidence": h.confidence, "frp": h.frp, "satellite": h.satellite,
         "acq_date": h.acq_date, "acq_time": h.acq_time, "daynight": h.daynight}
        for h in hotspots
    ]}


@router.get("/evacuations")
async def get_evacuations(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(EvacuationZone).where(EvacuationZone.is_active == True)
        .order_by(desc(EvacuationZone.collected_at))
    )
    zones = result.scalars().all()
    return {"count": len(zones), "evacuations": [
        {
            "id": z.id,
            "external_id": z.external_id,
            "event_name": z.event_name,
            "event_number": z.event_number,
            "event_type": z.event_type,
            "status": z.order_alert_status,
            "issuing_agency": z.issuing_agency,
            "homes_affected": z.homes_affected,
            "population_affected": z.population_affected,
            "latitude": z.latitude,
            "longitude": z.longitude,
            "event_start_date": z.event_start_date.isoformat() if z.event_start_date else None,
        }
        for z in zones
    ]}


@router.post("/analyze/text")
async def analyze_text(body: dict):
    text = body.get("text", "")
    if not text: raise HTTPException(400, "text field required")
    score, keywords, sentiment = nlp.analyze_text(text)
    location = nlp.extract_location(text)
    return {"fire_score": score, "is_fire_related": score >= settings.AI_DETECTION_THRESHOLD,
            "keywords": keywords, "sentiment": sentiment, "extracted_location": location,
            "threshold": settings.AI_DETECTION_THRESHOLD}


@router.get("/analysis/risk")
async def get_risk_assessment(session: AsyncSession = Depends(get_session)):
    cutoff = datetime.utcnow() - timedelta(hours=1)

    active_fires = (await session.execute(
        select(Incident).where(Incident.is_active == True, Incident.status == "active")
    )).scalars().all()
    social_count = (await session.execute(
        select(func.count(SocialPost.id)).where(
            SocialPost.collected_at >= cutoff, SocialPost.ai_fire_score >= settings.AI_DETECTION_THRESHOLD)
    )).scalar() or 0
    hotspot_count = (await session.execute(
        select(func.count(NASAHotspot.id)).where(NASAHotspot.collected_at >= cutoff)
    )).scalar() or 0
    weather = (await session.execute(
        select(WeatherReading).order_by(desc(WeatherReading.recorded_at)).limit(1)
    )).scalar_one_or_none()

    fire_pts = min(25, len(active_fires) * 8)
    sat_pts = min(25, hotspot_count * 5)
    soc_pts = min(25, social_count * 3)
    wx_pts = _wx_risk(weather)
    total = min(100, fire_pts + sat_pts + soc_pts + wx_pts)

    return {"risk_score": total, "rating": _risk_rating(total),
            "components": {
                "active_fires": {"score": fire_pts, "count": len(active_fires)},
                "satellite": {"score": sat_pts, "count": hotspot_count},
                "social": {"score": soc_pts, "count": social_count},
                "weather": {"score": wx_pts},
            }, "timestamp": datetime.utcnow().isoformat()}


@router.get("/dashboard/stats")
async def get_dashboard_stats(session: AsyncSession = Depends(get_session)):
    active = (await session.execute(select(func.count(Incident.id)).where(
        Incident.is_active == True, Incident.status == "active"))).scalar() or 0
    monitoring = (await session.execute(select(func.count(Incident.id)).where(
        Incident.is_active == True, Incident.status == "monitoring"))).scalar() or 0
    contained = (await session.execute(select(func.count(Incident.id)).where(
        Incident.is_active == True, Incident.status == "contained"))).scalar() or 0
    total_area = (await session.execute(
        select(func.sum(Incident.size_hectares)).where(Incident.is_active == True))).scalar() or 0.0
    alert_count = (await session.execute(select(func.count(Alert.id)).where(
        Alert.is_active == True, Alert.acknowledged == False,
        Alert.created_at >= datetime.utcnow() - timedelta(hours=24)))).scalar() or 0
    return {"active_fires": active, "monitoring": monitoring, "contained": contained,
            "total_area_ha": round(total_area, 1), "unacknowledged_alerts": alert_count,
            "timestamp": datetime.utcnow().isoformat()}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


def _ser_incident(i):
    return {"id": i.id, "external_id": i.external_id, "name": i.name,
            "latitude": i.latitude, "longitude": i.longitude,
            "status": i.status, "threat_level": i.threat_level,
            "size_hectares": i.size_hectares, "containment_pct": i.containment_pct,
            "source": i.source, "confidence": i.confidence,
            "fire_cause": i.fire_cause, "fire_number": i.fire_number,
            "geographic_desc": i.geographic_desc,
            "discovered_at": i.discovered_at.isoformat() if i.discovered_at else None,
            "updated_at": i.updated_at.isoformat() if i.updated_at else None}


def _fwi_rating(fwi):
    if fwi is None: return "Unknown"
    if fwi >= 30: return "Extreme"
    if fwi >= 20: return "Very High"
    if fwi >= 14: return "High"
    if fwi >= 8: return "Moderate"
    return "Low"


def _risk_rating(s):
    if s >= 85: return "CRITICAL"
    if s >= 60: return "HIGH"
    if s >= 30: return "MODERATE"
    return "LOW"


def _wx_risk(w):
    if not w: return 0
    pts = 0
    if w.temperature_c and w.temperature_c >= 35: pts += 8
    if w.humidity_pct and w.humidity_pct <= 15: pts += 8
    if w.wind_speed_kmh and w.wind_speed_kmh >= 40: pts += 7
    return min(pts, 25)
