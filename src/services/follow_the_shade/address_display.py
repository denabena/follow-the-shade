"""Normalize addresses for UI display (street/local line only)."""

from __future__ import annotations

import re

# Trailing clauses removed iteratively (order: longer country names first).
_LOCATION_SUFFIX_PATTERNS = (
    r",\s*Republic\s+of\s+Croatia\s*$",
    r",\s*Croatia\s*$",
    r",\s*Hrvatska\s*$",
    r",\s*Split\s*$",
)


def _tidy_commas_and_spaces(s: str) -> str:
    s = re.sub(r",\s*,", ",", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    return s.strip(" ,")


def format_address_for_display(address: str | None) -> str | None:
    """
    Keep only the street/local part: drop postal 21000 and trailing
    Split / Croatia (and common variants).
    """
    if address is None or not isinstance(address, str):
        return address
    original = address.strip()
    if not original:
        return address

    s = re.sub(r"\b21000\b", "", original, flags=re.IGNORECASE)
    s = _tidy_commas_and_spaces(s)

    changed = True
    while changed:
        changed = False
        for pat in _LOCATION_SUFFIX_PATTERNS:
            next_s = re.sub(pat, "", s, flags=re.IGNORECASE)
            if next_s != s:
                s = _tidy_commas_and_spaces(next_s)
                changed = True
                break

    s = _tidy_commas_and_spaces(s)
    if not s:
        return ""
    if re.fullmatch(r"Split", s.strip(), flags=re.IGNORECASE):
        return ""
    return s
