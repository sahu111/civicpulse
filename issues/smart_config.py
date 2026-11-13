"""Every tunable value for the rule-based recommendations. Edit here; no code changes needed.

These are simple keyword and distance rules, not a trained model.
"""

# ---- Category suggestion: keyword hits per category; title hits count double ----
CATEGORY_KEYWORDS = {
    "ROADS": ["pothole", "road", "crack", "speed breaker", "footpath", "pavement", "asphalt", "traffic"],
    "STREETLIGHT": ["street light", "streetlight", "lamp", "light pole", "dark", "bulb", "flicker", "flickering"],
    "WATER": ["water", "pipe", "leak", "leaking", "tap", "supply", "burst", "pressure"],
    "DRAINAGE": ["drain", "sewage", "sewer", "overflow", "overflowing", "waterlogging", "manhole", "gutter"],
    "SANITATION": ["garbage", "trash", "waste", "dump", "litter", "smell", "dustbin", "collected"],
    "ELECTRICITY": ["wire", "electric", "power", "transformer", "shock", "outage", "cable"],
    "PARKS": ["park", "garden", "bench", "swing", "swings", "tree", "playground", "grass"],
}
TITLE_WEIGHT = 2

# ---- Priority recommendation: base score + risk words - low-impact words + supporters ----
CATEGORY_BASE_SCORE = {
    "ELECTRICITY": 3, "DRAINAGE": 2, "WATER": 2, "ROADS": 2,
    "STREETLIGHT": 1, "SANITATION": 1, "PARKS": 0, "OTHER": 0,
}
RISK_WORDS = {
    "school": 2, "hospital": 2, "child": 2, "children": 2, "accident": 3, "injury": 3,
    "live wire": 3, "exposed": 2, "electrocution": 3, "fire": 3, "sewage": 2,
    "flood": 2, "collapsed": 2, "blocked": 1,
}
LOW_IMPACT_WORDS = {"minor": -1, "cosmetic": -1, "graffiti": -1, "small": -1, "paint": -1}
SUPPORTERS_FOR_BONUS = 5
SUPPORT_BONUS = 1
PRIORITY_THRESHOLDS = {"HIGH": 5, "MEDIUM": 2}  # score at or above -> priority; below MEDIUM -> LOW

# ---- Duplicate suggestion ----
DUPLICATE_RADIUS_M = 300
DUPLICATE_MIN_SCORE = 0.35
DUPLICATE_WEIGHTS = {"text": 0.6, "category": 0.2, "distance": 0.2}
STOPWORDS = {
    "the", "and", "for", "near", "with", "from", "this", "that", "are", "was", "has", "have",
    "not", "all", "our", "very", "outside", "there", "been", "since", "after", "into",
}

# ---- Hotspots: round coordinates to grid cells and count reports ----
HOTSPOT_CELL_DEG = 0.01  # about 1.1 km
HOTSPOT_MIN_COUNT = 3

# ---- Overdue: open reports older than the target for their priority ----
RESOLUTION_TARGET_HOURS = {"HIGH": 48, "MEDIUM": 120, "LOW": 240}
