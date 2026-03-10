"""
NLP Engine — Fire-related text analysis.
MVP: Weighted keyword matching + heuristic scoring.
"""

import re
import math
from typing import Optional

from core.config import settings


class NLPEngine:

    FIRE_DIRECT = {
        "fire": 3.0, "wildfire": 3.5, "flames": 3.0, "blaze": 3.0,
        "inferno": 3.0, "burning": 2.5, "ablaze": 3.0,
        "structure fire": 3.5, "brush fire": 3.0, "grass fire": 3.0,
        "interface fire": 3.0, "crown fire": 3.5,
        "feu": 3.0, "incendie": 3.5, "feu de foret": 3.5,
    }

    SMOKE_INDICATORS = {
        "smoke": 2.5, "smoky": 2.0, "haze": 1.5, "ash": 2.0,
        "embers": 2.5, "smoke plume": 3.0, "smoke cloud": 2.8,
        "fumee": 2.5, "air quality": 1.5,
    }

    EMERGENCY_INDICATORS = {
        "evacuate": 3.5, "evacuation": 3.5, "evacuation order": 4.0,
        "evacuation warning": 3.8, "evacuation alert": 3.8,
        "emergency": 3.0, "911": 3.5,
        "fire truck": 3.0, "fire department": 2.8,
        "firefighter": 2.5, "firefighters": 2.5,
        "air tanker": 3.0, "water bomber": 3.0,
        "fire crew": 2.8, "structure protection": 3.0,
        "evacuation": 3.5, "urgence": 3.0,
    }

    FIRE_TECHNICAL = {
        "containment": 2.0, "perimeter": 2.0, "hotspot": 2.0,
        "hectares": 1.8, "interface zone": 2.0,
        "fire weather": 2.5, "fire ban": 2.0,
        "bc wildfire": 3.0, "wildfire service": 2.8,
        "fire danger": 2.5, "out of control": 3.0,
        "being held": 2.5, "spreading": 2.5,
    }

    URGENCY_SIGNALS = {
        "help": 1.5, "danger": 2.0, "trapped": 3.0, "rescue": 2.5,
        "close to my house": 3.0, "coming towards": 2.5,
        "getting worse": 2.0, "need to leave": 3.0,
        "packing up": 2.5, "leaving now": 3.0,
    }

    FALSE_POSITIVES = {
        "campfire": -2.5, "fireplace": -2.5, "fire pit": -2.5,
        "fireworks": -2.0, "fire sale": -3.0, "fired from": -3.0,
        "fire station tour": -2.0, "fire drill": -2.0,
        "dumpster fire": -2.0, "roast": -1.0,
    }

    LOCAL_PLACES = [
        "kelowna", "west kelowna", "westbank", "peachland",
        "penticton", "vernon", "lake country", "summerland",
        "knox mountain", "dilworth mountain", "black mountain",
        "mission creek", "okanagan", "okanagan lake",
        "lakeshore", "pandosy", "rutland", "glenmore",
        "joe rich", "myra", "bellevue", "bear creek",
        "trepanier", "mcculloch", "gallagher canyon",
        "kettle valley", "crawford estates", "southeast kelowna",
        "upper mission", "lower mission", "south pandosy",
        "clifton", "mckenzie bench", "ellison", "winfield",
        "oyama", "carr's landing", "fintry", "killiney beach",
        "scotty creek", "rose valley", "glenrosa",
    ]

    URGENCY_PATTERNS = [
        r"\bright\s+now\b", r"\bcurrently\b", r"\bjust\s+saw\b",
        r"\bhappening\s+now\b", r"\bhelp\s+us\b", r"\bplease\s+help\b",
        r"\bget\s+out\b", r"\bleave\s+now\b", r"\bpacking\s+up\b",
    ]

    def __init__(self):
        self._all_keywords = {}
        for d in [self.FIRE_DIRECT, self.SMOKE_INDICATORS,
                  self.EMERGENCY_INDICATORS, self.FIRE_TECHNICAL,
                  self.URGENCY_SIGNALS]:
            self._all_keywords.update(d)

    def analyze_text(self, text: str) -> tuple[float, list[str], str]:
        if not text or len(text.strip()) < 5:
            return 0.0, [], "informational"

        text_lower = text.lower()
        total_weight = 0.0
        matched = []

        for keyword, weight in self._all_keywords.items():
            if keyword in text_lower:
                total_weight += weight
                matched.append(keyword)

        for keyword, weight in self.FALSE_POSITIVES.items():
            if keyword in text_lower:
                total_weight += weight

        loc_boost = 0
        for place in self.LOCAL_PLACES:
            if place in text_lower:
                loc_boost += 1.5
                matched.append(f"loc:{place}")
        total_weight += min(loc_boost, 4.0)

        urg_boost = 0
        for pattern in self.URGENCY_PATTERNS:
            if re.search(pattern, text_lower):
                urg_boost += 1.0
        total_weight += min(urg_boost, 3.0)

        score = 1 / (1 + math.exp(-0.5 * (total_weight - 4)))
        sentiment = self._classify_sentiment(text_lower, urg_boost)

        return round(score, 3), matched, sentiment

    def extract_location(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        found = [place.title() for place in self.LOCAL_PLACES if place in text_lower]
        street_re = r'(?:on|near|at|by|along)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Rd|St|Ave|Dr|Blvd|Way|Ln|Cres|Pl|Ct|Hwy|Road|Street|Drive))'
        found.extend(re.findall(street_re, text))
        hwy_re = r'(?:Highway|Hwy)\s+(\d+[A-Z]?)'
        found.extend([f"Hwy {h}" for h in re.findall(hwy_re, text, re.IGNORECASE)])
        return ", ".join(found[:5]) if found else None

    def _classify_sentiment(self, text, urgency_score):
        urgent_words = ["help", "trapped", "emergency", "hurry", "asap", "danger", "run"]
        concerned_words = ["worried", "scared", "nervous", "concerned", "preparing"]
        if urgency_score > 2 or sum(1 for w in urgent_words if w in text) >= 2:
            return "urgent"
        if any(w in text for w in concerned_words) or any(w in text for w in urgent_words):
            return "concerned"
        return "informational"

    def batch_analyze(self, texts: list[str]) -> dict:
        results = [self.analyze_text(t) for t in texts]
        fire_related = [r for r in results if r[0] >= settings.AI_DETECTION_THRESHOLD]
        all_kw = {}
        sentiments = {"urgent": 0, "concerned": 0, "informational": 0}
        for score, keywords, sentiment in fire_related:
            sentiments[sentiment] += 1
            for kw in keywords:
                if not kw.startswith("loc:"):
                    all_kw[kw] = all_kw.get(kw, 0) + 1
        return {
            "total": len(texts),
            "fire_related": len(fire_related),
            "avg_score": sum(r[0] for r in fire_related) / max(len(fire_related), 1),
            "top_keywords": sorted(all_kw.items(), key=lambda x: x[1], reverse=True)[:10],
            "sentiments": sentiments,
            "spike": len(fire_related) >= settings.SOCIAL_SPIKE_THRESHOLD,
        }
