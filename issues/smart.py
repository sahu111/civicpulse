"""Rule-based recommendations (keywords, scores, distance). Values live in smart_config.py."""
import re
from collections import Counter
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from django.db.models import Q
from django.utils import timezone

from . import smart_config as cfg
from .models import Category, Issue


def tokenize(text):
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in cfg.STOPWORDS]


def _hits(phrase, text):
    return len(re.findall(rf"\b{re.escape(phrase)}\b", (text or "").lower()))


def jaccard(a, b):
    A, B = set(tokenize(a)), set(tokenize(b))
    return len(A & B) / len(A | B) if A and B else 0.0


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dphi, dlmb = p2 - p1, radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * R * asin(sqrt(a))


def suggest_category(title, description=""):
    """Returns (category, matched_words). Category is "" when no keyword matched."""
    best, best_score, best_words = "", 0, []
    for cat, words in cfg.CATEGORY_KEYWORDS.items():
        score, matched = 0, []
        for w in words:
            n = _hits(w, title) * cfg.TITLE_WEIGHT + _hits(w, description)
            if n:
                score += n
                matched.append(w)
        if score > best_score:
            best, best_score, best_words = cat, score, matched
    return best, best_words


def recommend_priority(category, title, description="", supporters=0):
    """Returns (priority, reasons) where reasons is a plain-language list."""
    text = f"{title} {description}"
    score = cfg.CATEGORY_BASE_SCORE.get(category, 0)
    reasons = [f"{Category(category).label if category in Category.values else 'Category'} starts at {score} points"]
    for word, pts in list(cfg.RISK_WORDS.items()) + list(cfg.LOW_IMPACT_WORDS.items()):
        if _hits(word, text):
            score += pts
            reasons.append(f'Mentions "{word}" ({pts:+d})')
    if supporters >= cfg.SUPPORTERS_FOR_BONUS:
        score += cfg.SUPPORT_BONUS
        reasons.append(f"{supporters} people support this report ({cfg.SUPPORT_BONUS:+d})")
    if score >= cfg.PRIORITY_THRESHOLDS["HIGH"]:
        priority = "HIGH"
    elif score >= cfg.PRIORITY_THRESHOLDS["MEDIUM"]:
        priority = "MEDIUM"
    else:
        priority = "LOW"
    reasons.append(f"Total {score} points, so {Issue.Priority(priority).label.lower()} priority")
    return priority, reasons


def find_duplicates(title, description, category, lat, lng, candidates, exclude_pk=None, limit=5):
    """Open reports nearby with similar text. Closed and merged reports are ignored."""
    lat, lng = float(lat), float(lng)
    r = cfg.DUPLICATE_RADIUS_M
    dlat = r / 111_320
    dlng = r / (111_320 * max(cos(radians(lat)), 0.01))
    qs = candidates.filter(
        status__in=Issue.OPEN_STATUSES, merged_into__isnull=True,
        latitude__range=(lat - dlat, lat + dlat), longitude__range=(lng - dlng, lng + dlng),
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    w = cfg.DUPLICATE_WEIGHTS
    text = f"{title} {description}"
    found = []
    for issue in qs[:200]:
        dist = haversine_m(lat, lng, float(issue.latitude), float(issue.longitude))
        if dist > r:
            continue
        sim = jaccard(text, f"{issue.title} {issue.description}")
        score = w["text"] * sim + w["category"] * (issue.category == category) + w["distance"] * (1 - dist / r)
        if score >= cfg.DUPLICATE_MIN_SCORE:
            found.append({"issue": issue, "score": round(score, 2), "distance_m": round(dist), "similarity": round(sim, 2)})
    return sorted(found, key=lambda d: d["score"], reverse=True)[:limit]


def hotspots(queryset):
    """Grid cells with at least HOTSPOT_MIN_COUNT reports, busiest first."""
    size = cfg.HOTSPOT_CELL_DEG
    cells = Counter(
        (round(float(lat) / size), round(float(lng) / size))
        for lat, lng in queryset.values_list("latitude", "longitude")
    )
    return [
        {"lat": round(i * size, 4), "lng": round(j * size, 4), "count": n}
        for (i, j), n in cells.most_common() if n >= cfg.HOTSPOT_MIN_COUNT
    ]


def overdue_q(now=None):
    now = now or timezone.now()
    q = Q()
    for priority, hours in cfg.RESOLUTION_TARGET_HOURS.items():
        q |= Q(priority=priority, created_at__lt=now - timedelta(hours=hours))
    return Q(status__in=Issue.OPEN_STATUSES) & q
