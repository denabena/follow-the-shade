from __future__ import annotations

import logging
from typing import Any

import httpx
from shapely.geometry import Polygon

from services.shadow.shadow_engine import Building, haversine_m

log = logging.getLogger(__name__)

DEFAULT_OVERPASS_FALLBACK_URLS = (
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


def parse_meters(value: str) -> float:
    cleaned = value.strip().lower().replace("m", "").replace(",", ".")
    return float(cleaned)


def estimate_height_m(tags: dict[str, Any]) -> tuple[float, str]:
    if tags.get("height"):
        return parse_meters(str(tags["height"])), "exact_tag"
    if tags.get("building:height"):
        return parse_meters(str(tags["building:height"])), "exact_tag"
    if tags.get("building:levels"):
        return float(tags["building:levels"]) * 3.0, "levels_estimate"
    if tags.get("levels"):
        return float(tags["levels"]) * 3.0, "levels_estimate"
    return 9.0, "default_estimate"


def _bbox_from_center(
    center: dict[str, float], radius_m: float
) -> tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320.0
    lng_delta = radius_m / (
        111_320.0
        * max(
            0.2, abs(__import__("math").cos(__import__("math").radians(center["lat"])))
        )
    )
    south = center["lat"] - lat_delta
    north = center["lat"] + lat_delta
    west = center["lng"] - lng_delta
    east = center["lng"] + lng_delta
    return south, west, north, east


def _build_polygon(
    element: dict[str, Any], nodes: dict[int, tuple[float, float]]
) -> Polygon | None:
    if element["type"] != "way":
        return None
    node_ids = element.get("nodes", [])
    coords = []
    for node_id in node_ids:
        if node_id in nodes:
            lat, lng = nodes[node_id]
            coords.append((lng, lat))
    if len(coords) < 3:
        return None
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    polygon = Polygon(coords)
    return polygon if polygon.is_valid and not polygon.is_empty else None


class OverpassClient:
    def __init__(
        self, base_url: str, fallback_urls: tuple[str, ...] | None = None
    ) -> None:
        raw_urls = (base_url, *(fallback_urls or DEFAULT_OVERPASS_FALLBACK_URLS))
        deduped_urls: list[str] = []
        for url in raw_urls:
            cleaned = url.rstrip("/")
            if cleaned not in deduped_urls:
                deduped_urls.append(cleaned)
        self.base_urls = tuple(deduped_urls)

    async def fetch_buildings(
        self,
        center: dict[str, float],
        radius_m: float = 450.0,
    ) -> list[Building]:
        south, west, north, east = _bbox_from_center(center, radius_m)
        query = f"""
[out:json][timeout:25];
(
  way["building"]({south},{west},{north},{east});
  way["building:part"]({south},{west},{north},{east});
);
out body;
>;
out skel qt;
"""
        data = await self._post(query)
        return self._parse_buildings(data)

    async def fetch_outdoor_seating_near(
        self,
        center: dict[str, float],
        radius_m: float = 35.0,
    ) -> list[dict[str, Any]]:
        return await self.fetch_outdoor_seating(center, radius_m=radius_m)

    async def fetch_outdoor_seating(
        self,
        center: dict[str, float],
        radius_m: float = 450.0,
    ) -> list[dict[str, Any]]:
        south, west, north, east = _bbox_from_center(center, radius_m)
        query = f"""
[out:json][timeout:25];
(
  node["leisure"="outdoor_seating"]({south},{west},{north},{east});
  way["leisure"="outdoor_seating"]({south},{west},{north},{east});
);
out body center;
"""
        data = await self._post(query)
        return self._parse_outdoor_seating(data, center, radius_m)

    def _parse_outdoor_seating(
        self,
        data: dict[str, Any],
        center: dict[str, float],
        radius_m: float,
    ) -> list[dict[str, Any]]:
        results = []
        for element in data.get("elements", []):
            if element["type"] == "node":
                lat, lng = element["lat"], element["lon"]
            else:
                center_point = element.get("center", {})
                lat, lng = center_point.get("lat"), center_point.get("lon")
            if lat is None or lng is None:
                continue
            point = {"lat": lat, "lng": lng}
            if haversine_m(center, point) <= radius_m:
                results.append(
                    {
                        "lat": lat,
                        "lng": lng,
                        "tags": element.get("tags", {}),
                    }
                )
        return results

    async def _post(self, query: str) -> dict[str, Any]:
        timeout = httpx.Timeout(connect=8.0, read=25.0, write=15.0, pool=8.0)
        errors: list[str] = []
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "FollowTheShade/1.0",
                },
            ) as client:
                for url in self.base_urls:
                    for method_name in ("post-text", "get-data", "post-form"):
                        try:
                            if method_name == "post-text":
                                response = await client.post(
                                    url,
                                    content=query.encode("utf-8"),
                                    headers={
                                        "Content-Type": "text/plain; charset=utf-8"
                                    },
                                )
                            elif method_name == "get-data":
                                response = await client.get(url, params={"data": query})
                            else:
                                response = await client.post(url, data={"data": query})
                            response.raise_for_status()
                            return response.json()
                        except httpx.HTTPStatusError as exc:
                            errors.append(
                                f"{url} {method_name} -> {exc.response.status_code}: {_response_excerpt(exc.response)}"
                            )
                        except httpx.HTTPError as exc:
                            errors.append(
                                f"{url} {method_name} -> {type(exc).__name__}"
                            )
        except httpx.HTTPError as exc:
            errors.append(f"client setup -> {type(exc).__name__}: {exc}")

        if errors:
            log.warning(
                "Overpass request failed across %s attempts: %s",
                len(errors),
                " | ".join(errors[:4]),
            )
            return {"elements": []}

    def _parse_buildings(self, data: dict[str, Any]) -> list[Building]:
        elements = data.get("elements", [])
        nodes: dict[int, tuple[float, float]] = {}
        ways: list[dict[str, Any]] = []

        for element in elements:
            if element["type"] == "node":
                nodes[element["id"]] = (element["lat"], element["lon"])
            elif element["type"] == "way":
                tags = element.get("tags", {})
                if tags.get("building") or tags.get("building:part"):
                    ways.append(element)

        buildings: list[Building] = []
        height_estimated = False
        for element in ways:
            polygon = _build_polygon(element, nodes)
            if polygon is None:
                continue
            height_m, confidence = estimate_height_m(element.get("tags", {}))
            if confidence != "exact_tag":
                height_estimated = True
            buildings.append(
                Building(
                    polygon_wgs84=polygon,
                    height_m=height_m,
                    height_confidence=confidence,
                )
            )
        if height_estimated:
            log.debug("Some building heights were estimated from OSM tags")
        return buildings[:200]


def _response_excerpt(response: httpx.Response) -> str:
    text = response.text.strip()
    return text[:160] if text else "No response body."
