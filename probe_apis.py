from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Awaitable, Callable

import httpx

sys.path.insert(0, "src")

from services.geodata.overpass_client import OverpassClient

ROOT = Path(__file__).resolve().parent
CENTER = {"lat": 43.5081, "lng": 16.4391}


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in (".env", ".env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


CONFIG = load_env()


def _tts_model() -> str:
    configured = CONFIG.get("SONIOX_TTS_MODEL") or "tts-rt-v1"
    return "tts-rt-v1" if configured == "tts-rt-preview" else configured


async def timed(
    label: str,
    probe: Callable[[], Awaitable[tuple[int | str, int, str]]],
) -> None:
    started = time.perf_counter()
    try:
        status, count, detail = await probe()
    except Exception as exc:
        status, count, detail = "ERR", 0, f"{type(exc).__name__}: {exc}"
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    print(f"{label:<26} | {str(status):<8} | {elapsed_ms:<6} | {count:<5} | {detail}")


async def probe_google_places_new() -> tuple[int | str, int, str]:
    api_key = CONFIG.get("GOOGLE_PLACES_API_KEY") or CONFIG.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "SKIP", 0, "missing key"

    payload = {
        "includedTypes": ["cafe"],
        "maxResultCount": 5,
        "rankPreference": "POPULARITY",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": CENTER["lat"], "longitude": CENTER["lng"]},
                "radius": 900.0,
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.location,places.rating,places.outdoorSeating",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://places.googleapis.com/v1/places:searchNearby",
            json=payload,
            headers=headers,
        )
    if response.status_code != 200:
        return response.status_code, 0, _excerpt(response)
    return response.status_code, len(response.json().get("places", [])), "ok"


async def probe_google_places_legacy() -> tuple[int | str, int, str]:
    api_key = CONFIG.get("GOOGLE_PLACES_API_KEY") or CONFIG.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "SKIP", 0, "missing key"

    params = {
        "location": f"{CENTER['lat']},{CENTER['lng']}",
        "radius": "900",
        "type": "cafe",
        "key": api_key,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params=params,
        )
    data = response.json() if response.status_code == 200 else {}
    return response.status_code, len(data.get("results", [])), data.get("status", "ok")


async def probe_overpass_buildings() -> tuple[int | str, int, str]:
    client = OverpassClient(
        CONFIG.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    )
    buildings = await client.fetch_buildings(CENTER, radius_m=450)
    return (
        200 if buildings else "EMPTY",
        len(buildings),
        "ok" if buildings else "no buildings",
    )


async def probe_overpass_seating() -> tuple[int | str, int, str]:
    client = OverpassClient(
        CONFIG.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    )
    points = await client.fetch_outdoor_seating(CENTER, radius_m=900)
    return 200, len(points), "ok"


async def probe_open_meteo() -> tuple[int | str, int, str]:
    params = {
        "latitude": CENTER["lat"],
        "longitude": CENTER["lng"],
        "hourly": "cloud_cover,precipitation_probability",
        "timezone": "Europe/Zagreb",
        "start_date": "2026-05-16",
        "end_date": "2026-05-16",
    }
    base_url = CONFIG.get(
        "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1"
    ).rstrip("/")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{base_url}/forecast", params=params)
    if response.status_code != 200:
        return response.status_code, 0, _excerpt(response)
    return (
        response.status_code,
        len(response.json().get("hourly", {}).get("time", [])),
        "ok",
    )


async def probe_soniox_temp_key(usage_type: str) -> tuple[int | str, int, str]:
    api_key = CONFIG.get("SONIOX_API_KEY")
    if not api_key:
        return "SKIP", 0, "missing key"

    payload = {
        "usage_type": usage_type,
        "expires_in_seconds": 60,
        "client_reference_id": "api-audit",
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://api.soniox.com/v1/auth/temporary-api-key",
            json=payload,
            headers=headers,
        )
    detail = "ok" if response.status_code == 201 else _excerpt(response)
    return response.status_code, 1 if response.status_code == 201 else 0, detail


async def probe_soniox_rest_tts() -> tuple[int | str, int, str]:
    api_key = CONFIG.get("SONIOX_API_KEY_TTS") or CONFIG.get("SONIOX_API_KEY")
    if not api_key:
        return "SKIP", 0, "missing key"

    payload = {
        "model": _tts_model(),
        "language": CONFIG.get("SONIOX_TTS_LANGUAGE", "en"),
        "voice": CONFIG.get("SONIOX_TTS_VOICE", "Grace"),
        "audio_format": CONFIG.get("SONIOX_TTS_AUDIO_FORMAT", "mp3"),
        "text": "Split shade test.",
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            CONFIG.get("SONIOX_API_HOST_TTS", "https://tts-rt.soniox.com/tts"),
            json=payload,
            headers=headers,
        )
    detail = (
        "ok" if response.status_code == 200 and response.content else _excerpt(response)
    )
    return response.status_code, len(response.content), detail


async def probe_mapbox_style() -> tuple[int | str, int, str]:
    token = CONFIG.get("NEXT_PUBLIC_MAPBOX_TOKEN")
    if not token:
        return "SKIP", 0, "missing token"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://api.mapbox.com/styles/v1/mapbox/standard",
            params={"access_token": token},
        )
    return (
        response.status_code,
        1 if response.status_code == 200 else 0,
        "ok" if response.status_code == 200 else _excerpt(response),
    )


async def probe_shademap_sdk() -> tuple[int | str, int, str]:
    api_key = CONFIG.get("NEXT_PUBLIC_SHADEMAP_API_KEY") or CONFIG.get(
        "SHADEMAP_API_KEY"
    )
    if not api_key:
        return "SKIP", 0, "missing key"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://shademap.app/sdk/load", json={"api_key": api_key}
        )
    return (
        response.status_code,
        1 if response.status_code == 200 else 0,
        "ok" if response.status_code == 200 else _excerpt(response),
    )


def _excerpt(response: httpx.Response) -> str:
    return response.text.strip().replace("\n", " ")[:120] or "no response body"


async def main() -> None:
    print(f"{'Provider':<26} | {'Status':<8} | {'ms':<6} | {'Count':<5} | Detail")
    print("-" * 82)
    await timed("Google Places New", probe_google_places_new)
    await timed("Google Places Legacy", probe_google_places_legacy)
    await timed("Overpass Buildings", probe_overpass_buildings)
    await timed("Overpass Seating", probe_overpass_seating)
    await timed("Open-Meteo", probe_open_meteo)
    await timed(
        "Soniox Temp STT", lambda: probe_soniox_temp_key("transcribe_websocket")
    )
    await timed("Soniox Temp TTS", lambda: probe_soniox_temp_key("tts_rt"))
    await timed("Soniox REST TTS", probe_soniox_rest_tts)
    await timed("Mapbox Style", probe_mapbox_style)
    await timed("ShadeMap SDK Load", probe_shademap_sdk)


if __name__ == "__main__":
    asyncio.run(main())
