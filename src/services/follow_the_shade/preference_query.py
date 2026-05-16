from __future__ import annotations

import re
from typing import Any


def enrich_query_with_preferences(query: str, prefs: dict[str, Any]) -> str:
    normalized = query.lower()
    parts = [query.strip()]

    preference = prefs.get("exposure_preference", "either")
    has_sun = bool(re.search(r"\b(sun|sunny|sunlight|sunce)\b", normalized))
    has_shade = bool(re.search(r"\b(shade|shady|shadow|hlad|sjena)\b", normalized))
    if preference in {"sun", "shade"} and not (has_sun or has_shade):
        if preference == "shade":
            parts.append("I prefer shade.")
        if preference == "sun":
            parts.append("I prefer sun.")

    areas = prefs.get("favorite_areas") or []
    if areas and not _mentions_split_area(normalized):
        parts.append(f"Near {areas[0]}.")

    if not _mentions_time(normalized):
        preset = prefs.get("default_time_preset", "afternoon")
        parts.append(f"This {preset} today.")

    if prefs.get("avoid_busy") and "busy" not in normalized and "crowd" not in normalized:
        parts.append("Not too busy.")

    return " ".join(part for part in parts if part)


def _mentions_split_area(normalized: str) -> bool:
    markers = (
        "riva",
        "bacvice",
        "marmontova",
        "varos",
        "znjan",
        "split",
        "palace",
        "pjaca",
        "matejuska",
        "prokurative",
    )
    return any(marker in normalized for marker in markers)


def _mentions_time(normalized: str) -> bool:
    if re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)?\b", normalized):
        return True
    return any(
        token in normalized
        for token in ("morning", "afternoon", "lunch", "today", "tomorrow", "from", "until")
    )
