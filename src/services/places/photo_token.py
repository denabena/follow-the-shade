"""Opaque base64url tokens for Google Places photo proxy (no secrets in payload)."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any, Literal

MAX_JSON_BYTES = 2048


def encode_place_photo_p(
    *,
    variant: Literal["new", "legacy"],
    name: str | None = None,
    ref: str | None = None,
) -> str | None:
    if variant == "new" and name and isinstance(name, str):
        payload: dict[str, str] = {"v": "new", "name": name.strip()}
    elif variant == "legacy" and ref and isinstance(ref, str):
        payload = {"v": "legacy", "ref": ref.strip()}
    else:
        return None
    if not payload.get("name") and not payload.get("ref"):
        return None
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_JSON_BYTES:
        return None
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_place_photo_p(p: str) -> dict[str, str] | None:
    token = p.strip()
    if not token or len(token) > 4096:
        return None
    pad = (-len(token)) % 4
    if pad:
        token += "=" * pad
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except (ValueError, binascii.Error):
        return None
    if len(raw) > MAX_JSON_BYTES:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    v = data.get("v")
    if v == "new":
        name = data.get("name")
        if isinstance(name, str) and name.strip():
            return {"v": "new", "name": name.strip()}
    elif v == "legacy":
        ref = data.get("ref")
        if isinstance(ref, str) and ref.strip():
            return {"v": "legacy", "ref": ref.strip()}
    return None


def place_photo_p_from_cafe(cafe: dict[str, Any]) -> str | None:
    name = cafe.get("place_photo_name")
    if isinstance(name, str) and name.strip():
        return encode_place_photo_p(variant="new", name=name)
    ref = cafe.get("photo_reference")
    if isinstance(ref, str) and ref.strip():
        return encode_place_photo_p(variant="legacy", ref=ref)
    existing = cafe.get("place_photo_p")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    return None
