from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Response

from core.config import settings
from services.places.photo_media import fetch_place_photo_bytes
from services.places.photo_token import decode_place_photo_p

log = logging.getLogger(__name__)

router = APIRouter(prefix="/places", tags=["places"])


def _places_api_key() -> str | None:
    return settings.GOOGLE_PLACES_API_KEY or settings.GOOGLE_MAPS_API_KEY


@router.get("/photo")
async def place_photo(p: str) -> Response:
    spec = decode_place_photo_p(p)
    if spec is None:
        raise HTTPException(status_code=400, detail="invalid_photo_token")

    api_key = _places_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="google_places_not_configured")

    try:
        data, media_type = await fetch_place_photo_bytes(api_key, spec)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code if exc.response is not None else 502
        log.warning("Google place photo HTTP error: %s", code)
        raise HTTPException(status_code=404, detail="photo_not_found") from exc
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Google place photo fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="photo_fetch_failed") from exc

    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )
