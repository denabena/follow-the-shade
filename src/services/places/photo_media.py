"""Download place photo bytes from Google (Places API v1 or legacy Places Photo)."""

from __future__ import annotations

import httpx

DEFAULT_MAX_WIDTH = 800


async def fetch_place_photo_bytes(
    api_key: str,
    spec: dict[str, str],
    *,
    max_width_px: int = DEFAULT_MAX_WIDTH,
) -> tuple[bytes, str]:
    if spec.get("v") == "new":
        return await _fetch_new_photo(api_key, spec["name"], max_width_px=max_width_px)
    if spec.get("v") == "legacy":
        return await _fetch_legacy_photo(
            api_key, spec["ref"], max_width_px=max_width_px
        )
    raise ValueError("invalid photo spec")


async def _fetch_new_photo(
    api_key: str, resource_name: str, *, max_width_px: int
) -> tuple[bytes, str]:
    # Resource name is `places/{placeId}/photos/{photo}` — slashes must stay as
    # path separators. Fully quoting (safe="") turns `/` into `%2F` and breaks getMedia.
    url = f"https://places.googleapis.com/v1/{resource_name}/media"
    params = {"maxWidthPx": max_width_px}
    headers = {"X-Goog-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "image/jpeg")
        return response.content, content_type.split(";")[0].strip() or "image/jpeg"


async def _fetch_legacy_photo(
    api_key: str, photo_reference: str, *, max_width_px: int
) -> tuple[bytes, str]:
    url = "https://maps.googleapis.com/maps/api/place/photo"
    params = {
        "maxwidth": max_width_px,
        "photo_reference": photo_reference,
        "key": api_key,
    }
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "image/jpeg")
        return response.content, content_type.split(";")[0].strip() or "image/jpeg"
