"""
Social Media & News Scanner — Reddit + RSS feeds.
Reddit: Public JSON (no auth). RSS: feedparser.
"""

import json
import re
import hashlib
import logging
from datetime import datetime, timedelta

import httpx
import feedparser
from sqlalchemy import select, func

from core.config import settings
from core.database import async_session, SocialPost, Alert
from services.nlp_engine import NLPEngine

logger = logging.getLogger(__name__)
nlp = NLPEngine()


async def scan_social_media() -> dict:
    logger.info("[Social] Scanning social media and news feeds...")
    stats = {"reddit_scanned": 0, "news_scanned": 0, "fire_related": 0, "stored": 0, "spike_alert": False, "errors": []}

    raw_posts = []

    # Reddit
    for sub in settings.REDDIT_SUBREDDITS:
        try:
            posts = await _scan_reddit(sub)
            raw_posts.extend(posts)
            stats["reddit_scanned"] += len(posts)
        except Exception as e:
            stats["errors"].append(f"Reddit r/{sub}: {str(e)[:100]}")

    # RSS
    for feed_cfg in settings.NEWS_FEEDS:
        try:
            posts = await _scan_rss(feed_cfg["name"], feed_cfg["url"])
            raw_posts.extend(posts)
            stats["news_scanned"] += len(posts)
        except Exception as e:
            stats["errors"].append(f"RSS {feed_cfg['name']}: {str(e)[:100]}")

    # NLP + store
    async with async_session() as session:
        for post in raw_posts:
            text = post.get("text", "")
            if not text or len(text) < 10:
                continue

            score, keywords, sentiment = nlp.analyze_text(text)
            if score < settings.AI_DETECTION_THRESHOLD:
                continue

            stats["fire_related"] += 1

            ext_id = post.get("external_id")
            if ext_id:
                existing = await session.execute(
                    select(SocialPost).where(SocialPost.external_id == ext_id)
                )
                if existing.scalar_one_or_none():
                    continue

            location = nlp.extract_location(text)
            social = SocialPost(
                platform=post.get("platform", "unknown"),
                external_id=ext_id,
                username=post.get("username", "unknown"),
                text=text[:2000], url=post.get("url"),
                ai_fire_score=score,
                detected_keywords=json.dumps(keywords),
                location_text=location, sentiment=sentiment,
            )
            session.add(social)
            stats["stored"] += 1

        await session.commit()

        # Spike check
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        count_result = await session.execute(
            select(func.count(SocialPost.id)).where(
                SocialPost.collected_at >= cutoff,
                SocialPost.ai_fire_score >= settings.AI_DETECTION_THRESHOLD,
            )
        )
        recent_count = count_result.scalar() or 0

        if recent_count >= settings.SOCIAL_SPIKE_THRESHOLD:
            stats["spike_alert"] = True
            alert = Alert(
                alert_type="social_media",
                severity="HIGH" if recent_count > 15 else "MODERATE",
                area="Kelowna Region",
                message=f"AI detected {recent_count} fire-related posts in the last 30 minutes across social media and news.",
                source_count=recent_count,
            )
            session.add(alert)
            await session.commit()

    logger.info(f"[Social] Done — Reddit: {stats['reddit_scanned']}, News: {stats['news_scanned']}, Fire: {stats['fire_related']}")
    return stats


async def _scan_reddit(subreddit: str) -> list:
    posts = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {"q": "fire OR wildfire OR smoke OR evacuation", "sort": "new", "t": "day", "limit": 25, "restrict_sr": "true"}
        headers = {"User-Agent": settings.REDDIT_USER_AGENT}

        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 429:
            logger.warning(f"[Social] Reddit rate limited on r/{subreddit}")
            return posts
        if resp.status_code != 200:
            return posts

        data = resp.json()
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            text = f"{d.get('title', '')} {d.get('selftext', '')}".strip()
            if text:
                posts.append({
                    "platform": "Reddit",
                    "external_id": f"reddit_{d.get('id', '')}" if d.get("id") else None,
                    "username": f"u/{d.get('author', 'unknown')}",
                    "text": text,
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                })
    return posts


async def _scan_rss(name: str, url: str) -> list:
    posts = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            return posts

    feed = feedparser.parse(resp.content)
    for entry in feed.entries[:15]:
        title = entry.get("title", "")
        summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))
        text = f"{title} {summary}".strip()
        if text:
            link = entry.get("link", "")
            entry_id = entry.get("id", link)
            posts.append({
                "platform": name,
                "external_id": f"rss_{hashlib.md5(entry_id.encode()).hexdigest()[:16]}",
                "username": name,
                "text": text[:2000],
                "url": link,
            })
    return posts
