"""
Reddit Poster — Automated fire updates to r/kelowna and r/britishcolumbia.

Posts are triggered by:
  - New active fire incident detected
  - Evacuation order/alert issued
  - NASA satellite hotspot cluster (3+ hotspots)
  - Critical AI risk score (>=85)

Requires Reddit app credentials in .env (see .env.example).
Configure at: https://www.reddit.com/prefs/apps (script-type app)
"""

import asyncio
import logging
from datetime import datetime, timedelta

import praw
from sqlalchemy import select, func, desc

from core.config import settings
from core.database import (
    async_session, Incident, EvacuationZone,
    NASAHotspot, WeatherReading, RedditPost,
)

logger = logging.getLogger(__name__)


def _get_reddit_client():
    """Returns a PRAW Reddit instance, or None if credentials are not configured."""
    if not all([
        settings.REDDIT_CLIENT_ID,
        settings.REDDIT_CLIENT_SECRET,
        settings.REDDIT_USERNAME,
        settings.REDDIT_PASSWORD,
    ]):
        return None
    return praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        username=settings.REDDIT_USERNAME,
        password=settings.REDDIT_PASSWORD,
        user_agent=settings.REDDIT_BOT_USER_AGENT,
    )


async def run_reddit_poster() -> dict:
    stats = {"posted": 0, "skipped": 0, "errors": []}

    reddit = _get_reddit_client()
    if reddit is None:
        logger.info("[Reddit] Credentials not configured — skipping post run")
        stats["skipped"] = 1
        return stats

    try:
        posts_to_make = await _gather_posts()
        for post in posts_to_make:
            await _submit_post(reddit, post, stats)
            await asyncio.sleep(2)  # be polite to the API
    except Exception as e:
        stats["errors"].append(str(e)[:200])
        logger.error(f"[Reddit] Unexpected error: {e}", exc_info=True)

    logger.info(f"[Reddit] Done — posted={stats['posted']} skipped={stats['skipped']} errors={len(stats['errors'])}")
    return stats


async def _gather_posts() -> list[dict]:
    """Build the list of posts that should go out, deduped against reddit_posts table."""
    candidates = []

    async with async_session() as session:
        # 1. New active fire incidents (not yet posted)
        active_fires = (await session.execute(
            select(Incident).where(Incident.is_active == True, Incident.status == "active")
        )).scalars().all()

        for fire in active_fires:
            key = f"incident_{fire.external_id}"
            if not await _already_posted(session, key):
                candidates.append(_build_fire_post(fire, key))

        # 2. Active evacuation orders/alerts (not yet posted)
        evac_zones = (await session.execute(
            select(EvacuationZone).where(EvacuationZone.is_active == True)
        )).scalars().all()

        for zone in evac_zones:
            key = f"evac_{zone.external_id}"
            if not await _already_posted(session, key):
                candidates.append(_build_evac_post(zone, key))

        # 3. NASA hotspot cluster in the last hour (3+ hotspots, post once per hour)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        hotspot_count = (await session.execute(
            select(func.count(NASAHotspot.id)).where(NASAHotspot.collected_at >= cutoff)
        )).scalar() or 0

        if hotspot_count >= 3:
            hour_key = f"hotspots_{datetime.utcnow().strftime('%Y%m%d_%H')}"
            if not await _already_posted(session, hour_key):
                weather = (await session.execute(
                    select(WeatherReading).order_by(desc(WeatherReading.recorded_at)).limit(1)
                )).scalar_one_or_none()
                candidates.append(_build_hotspot_post(hotspot_count, weather, hour_key))

    return candidates


async def _already_posted(session, event_key: str) -> bool:
    result = await session.execute(
        select(RedditPost).where(RedditPost.event_key == event_key)
    )
    return result.scalar_one_or_none() is not None


async def _submit_post(reddit, post: dict, stats: dict):
    subreddit_name = post["subreddit"]
    async with async_session() as session:
        try:
            # PRAW is sync — run in thread to avoid blocking the event loop
            submission = await asyncio.to_thread(
                lambda: reddit.subreddit(subreddit_name).submit(
                    title=post["title"],
                    selftext=post["body"],
                    flair_id=None,
                )
            )
            record = RedditPost(
                subreddit=subreddit_name,
                event_key=post["event_key"],
                title=post["title"],
                body=post["body"],
                reddit_post_id=submission.id,
            )
            session.add(record)
            await session.commit()
            stats["posted"] += 1
            logger.info(f"[Reddit] Posted to r/{subreddit_name}: {post['title']} → https://redd.it/{submission.id}")
        except Exception as e:
            stats["errors"].append(f"r/{subreddit_name}: {str(e)[:150]}")
            logger.error(f"[Reddit] Failed to post to r/{subreddit_name}: {e}")
            # Still save to DB so we don't retry the same event forever
            record = RedditPost(
                subreddit=subreddit_name,
                event_key=post["event_key"],
                title=post["title"],
                body=post["body"],
                reddit_post_id=None,
            )
            session.add(record)
            await session.commit()


# ── Post builders ──────────────────────────────────────────────

def _build_fire_post(fire: "Incident", event_key: str) -> dict:
    size = f"{fire.size_hectares:.1f} ha" if fire.size_hectares else "size unknown"
    threat = fire.threat_level or "MODERATE"
    cause = fire.fire_cause or "Unknown"
    title = f"[KelownaFireGuard] Active wildfire detected near Kelowna — {fire.name} ({size}, {threat})"
    body = (
        f"**KelownaFireGuard** has detected an active wildfire in the Central Okanagan region.\n\n"
        f"| | |\n|---|---|\n"
        f"| **Fire** | {fire.name} |\n"
        f"| **Status** | {fire.status.capitalize()} |\n"
        f"| **Threat Level** | {threat} |\n"
        f"| **Size** | {size} |\n"
        f"| **Cause** | {cause} |\n"
        f"| **Coordinates** | {fire.latitude:.4f}°N, {abs(fire.longitude):.4f}°W |\n"
        f"| **Source** | {fire.source} |\n\n"
        f"Monitor the situation at the [BC Wildfire Service Dashboard](https://wildfiresituation.nrs.gov.bc.ca/).\n\n"
        f"*This post was generated automatically by KelownaFireGuard, "
        f"an open-source AI wildfire monitoring system for Kelowna, BC.*"
    )
    return {"subreddit": "kelowna", "event_key": event_key, "title": title, "body": body}


def _build_evac_post(zone: "EvacuationZone", event_key: str) -> dict:
    status = zone.order_alert_status or "Alert"
    homes = f"{zone.homes_affected:,}" if zone.homes_affected else "unknown"
    title = f"[KelownaFireGuard] Evacuation {status} — {zone.event_name}"
    body = (
        f"**KelownaFireGuard** has detected an active evacuation {status.lower()} in the Central Okanagan.\n\n"
        f"| | |\n|---|---|\n"
        f"| **Event** | {zone.event_name} |\n"
        f"| **Status** | {status} |\n"
        f"| **Issuing Agency** | {zone.issuing_agency or 'BC Government'} |\n"
        f"| **Homes Affected** | {homes} |\n\n"
        f"Follow official updates at [Emergency Info BC](https://www.emergencyinfobc.gov.bc.ca/) "
        f"and [BC Government Evacuation Orders](https://www2.gov.bc.ca/gov/content/safety/emergency-preparedness-response-recovery/emergency-response/evacuation-orders-alerts).\n\n"
        f"*This post was generated automatically by KelownaFireGuard, "
        f"an open-source AI wildfire monitoring system for Kelowna, BC.*"
    )
    return {"subreddit": "kelowna", "event_key": event_key, "title": title, "body": body}


def _build_hotspot_post(count: int, weather: "WeatherReading | None", event_key: str) -> dict:
    wx_line = ""
    if weather:
        wx_line = (
            f"\n\n**Current conditions:** "
            f"{weather.temperature_c:.1f}°C · "
            f"{weather.humidity_pct:.0f}% RH · "
            f"Wind {weather.wind_speed_kmh:.0f} km/h {weather.wind_direction or ''} · "
            f"FWI {weather.fire_weather_index or 'N/A'}"
        )
    title = f"[KelownaFireGuard] {count} satellite fire hotspot(s) detected near Kelowna in the last hour"
    body = (
        f"**KelownaFireGuard** has detected **{count} satellite thermal hotspot(s)** "
        f"in the Kelowna / Central Okanagan region in the past hour, "
        f"based on NASA FIRMS VIIRS data.{wx_line}\n\n"
        f"This may indicate active burning. Monitor the [BC Wildfire Service Dashboard]"
        f"(https://wildfiresituation.nrs.gov.bc.ca/) for official confirmation.\n\n"
        f"*This post was generated automatically by KelownaFireGuard, "
        f"an open-source AI wildfire monitoring system for Kelowna, BC.*"
    )
    return {"subreddit": "kelowna", "event_key": event_key, "title": title, "body": body}
