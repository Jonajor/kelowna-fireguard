"""
Weather — Environment Canada + OpenWeatherMap.
Primary: EC citypage XML (free, no auth)
Secondary: OpenWeatherMap (free tier, 1000/day) for AQI/UV
"""

import logging
import re
from datetime import datetime, timezone
from xml.etree import ElementTree

import httpx

from core.config import settings
from core.database import async_session, WeatherReading, Alert

logger = logging.getLogger(__name__)


async def collect_weather_data() -> dict:
    logger.info("[Weather] Collecting weather data...")
    stats = {"source": None, "alerts_created": 0, "errors": []}

    reading = WeatherReading(
        station_id=settings.EC_STATION_ID,
        source="environment_canada",
        recorded_at=datetime.utcnow(),
    )

    # 1. Environment Canada
    try:
        ec = await _fetch_environment_canada()
        if ec:
            reading.temperature_c = ec.get("temperature")
            reading.humidity_pct = ec.get("humidity")
            reading.wind_speed_kmh = ec.get("wind_speed")
            reading.wind_gust_kmh = ec.get("wind_gust")
            reading.wind_direction = ec.get("wind_direction")
            reading.pressure_hpa = ec.get("pressure")
            reading.dew_point_c = ec.get("dew_point")
            reading.visibility_km = ec.get("visibility")
            reading.condition_text = ec.get("condition")
            stats["source"] = "environment_canada"
            logger.info(f"[Weather] EC: {reading.temperature_c}°C, {reading.humidity_pct}%RH, wind {reading.wind_speed_kmh} km/h")
    except Exception as e:
        stats["errors"].append(f"EC: {str(e)[:100]}")
        logger.error(f"[Weather] EC error: {e}")

    # 2. OpenWeatherMap (AQI, UV)
    if settings.OPENWEATHER_API_KEY:
        try:
            owm = await _fetch_openweathermap()
            if owm:
                reading.aqi = owm.get("aqi")
                reading.uv_index = owm.get("uv_index")
                if reading.temperature_c is None:
                    reading.temperature_c = owm.get("temperature")
                    reading.humidity_pct = owm.get("humidity")
                    reading.wind_speed_kmh = owm.get("wind_speed")
                    reading.pressure_hpa = owm.get("pressure")
                    reading.source = "openweathermap"
                    stats["source"] = "openweathermap"
        except Exception as e:
            stats["errors"].append(f"OWM: {str(e)[:100]}")
            logger.warning(f"[Weather] OWM error: {e}")

    # 3. FWI estimate
    reading.fire_weather_index = _estimate_fwi(reading)

    # 4. Store + check alerts
    async with async_session() as session:
        session.add(reading)
        stats["alerts_created"] = await _check_fire_weather_alerts(session, reading)
        await session.commit()

    logger.info(f"[Weather] Done — FWI={reading.fire_weather_index}, alerts={stats['alerts_created']}")
    return stats


async def _fetch_environment_canada():
    # New EC format (post June 2025): files are in hourly UTC subdirectories
    hour = datetime.now(timezone.utc).strftime("%H")
    dir_url = f"{settings.EC_CITYPAGE_BASE_URL}/{hour}/"

    async with httpx.AsyncClient(timeout=20.0) as client:
        listing = await client.get(dir_url)
        listing.raise_for_status()

        # Find the latest _en.xml file for this station
        pattern = rf'href="([^"]*{re.escape(settings.EC_STATION_ID)}_en\.xml)"'
        matches = re.findall(pattern, listing.text)
        if not matches:
            raise ValueError(f"No EC file found for station {settings.EC_STATION_ID} in {dir_url}")
        latest_file = matches[-1]  # last = most recent timestamp

        resp = await client.get(f"{dir_url}{latest_file}")
        resp.raise_for_status()

    root = ElementTree.fromstring(resp.content)
    current = root.find(".//currentConditions")
    if current is None:
        return None

    data = {}
    for tag, key in [("temperature", "temperature"), ("relativeHumidity", "humidity"),
                      ("dewpoint", "dew_point"), ("visibility", "visibility")]:
        elem = current.find(tag)
        if elem is not None and elem.text:
            data[key] = _safe_float(elem.text)

    pressure = current.find("pressure")
    if pressure is not None and pressure.text:
        data["pressure"] = _safe_float(pressure.text) * 10  # kPa -> hPa

    wind = current.find("wind")
    if wind is not None:
        speed = wind.find("speed")
        gust = wind.find("gust")
        direction = wind.find("direction")
        if speed is not None and speed.text:
            data["wind_speed"] = _safe_float(speed.text)
        if gust is not None and gust.text:
            data["wind_gust"] = _safe_float(gust.text)
        if direction is not None and direction.text:
            data["wind_direction"] = direction.text

    cond = current.find("condition")
    if cond is not None and cond.text:
        data["condition"] = cond.text

    return data if data else None


async def _fetch_openweathermap():
    if not settings.OPENWEATHER_API_KEY:
        return None

    data = {}
    params = {
        "lat": settings.KELOWNA_LAT, "lon": settings.KELOWNA_LNG,
        "appid": settings.OPENWEATHER_API_KEY, "units": "metric",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{settings.OPENWEATHER_BASE_URL}/weather", params=params)
        if resp.status_code == 200:
            w = resp.json()
            data["temperature"] = w.get("main", {}).get("temp")
            data["humidity"] = w.get("main", {}).get("humidity")
            data["pressure"] = w.get("main", {}).get("pressure")
            data["wind_speed"] = (w.get("wind", {}).get("speed", 0) or 0) * 3.6

        aqi_resp = await client.get(settings.OPENWEATHER_AQI_URL, params=params)
        if aqi_resp.status_code == 200:
            items = aqi_resp.json().get("list", [])
            if items:
                pm25 = items[0].get("components", {}).get("pm2_5", 0)
                data["aqi"] = _pm25_to_aqi(pm25)

    return data if data else None


async def _check_fire_weather_alerts(session, reading):
    conditions = []
    if reading.temperature_c is not None and reading.temperature_c >= settings.TEMP_ALERT_C:
        conditions.append(f"Temperature {reading.temperature_c:.1f}°C")
    if reading.humidity_pct is not None and reading.humidity_pct <= settings.HUMIDITY_ALERT_PCT:
        conditions.append(f"Humidity {reading.humidity_pct:.0f}%")
    if reading.wind_speed_kmh is not None and reading.wind_speed_kmh >= settings.WIND_ALERT_KMH:
        conditions.append(f"Wind {reading.wind_speed_kmh:.0f} km/h")
    if reading.aqi is not None and reading.aqi > 150:
        conditions.append(f"AQI {reading.aqi}")

    if len(conditions) >= 2:
        alert = Alert(
            alert_type="weather_alert",
            severity="CRITICAL" if len(conditions) >= 3 else "HIGH",
            area="Central Okanagan — Kelowna",
            message=f"Extreme fire weather: {', '.join(conditions)}. FWI: {reading.fire_weather_index or 'N/A'}.",
            source_count=len(conditions),
        )
        session.add(alert)
        return 1
    return 0


def _estimate_fwi(reading):
    temp = reading.temperature_c
    humid = reading.humidity_pct
    wind = reading.wind_speed_kmh
    if temp is None or humid is None:
        return None
    return round(
        max(0, (temp - 10)) * 0.8 +
        max(0, (60 - (humid or 60))) * 0.5 +
        ((wind or 0)) * 0.3, 1
    )


def _pm25_to_aqi(pm25):
    if pm25 <= 12: return int(pm25 * 50 / 12)
    if pm25 <= 35.4: return int(50 + (pm25 - 12) * 50 / 23.4)
    if pm25 <= 55.4: return int(100 + (pm25 - 35.4) * 50 / 20)
    if pm25 <= 150.4: return int(150 + (pm25 - 55.4) * 50 / 95)
    return int(200 + (pm25 - 150.4) * 100 / 100)


def _safe_float(val, default=None):
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default
