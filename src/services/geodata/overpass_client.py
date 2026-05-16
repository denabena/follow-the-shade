from __future__ import annotations

import logging
import math
from typing import Any

import httpx
from shapely.geometry import Polygon

from services.shadow.shadow_engine import Building, haversine_m

log = logging.getLogger(__name__)


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
    center: dict[str, float],
    radius_m: float,
) -> tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320.0
    lng_delta = radius_m / (
        111_320.0 * max(0.2, abs(math.cos(math.radians(center["lat"]))))
    )
    south = center["lat"] - lat_delta
    north = center["lat"] + lat_delta
    west = center["lng"] - lng_delta
    east = center["lng"] + lng_delta
    return south, west, north, east


def _build_polygon(
    element: dict[str, Any],
    nodes: dict[int, tuple[float, float]],
) -> Polygon | None:
    if element["type"] != "way":
        return None
    coords = []
    for node_id in element.get("nodes", []):
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
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

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
                results.append({"lat": lat, "lng": lng, "tags": element.get("tags", {})})
        return results

    async def _post(self, query: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.base_url, data={"data": query})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            log.warning("Overpass request failed: %s", exc)
            return {"elements": []}

    def _parse_buildings(self, data: dict[str, Any]) -> list[Building]:
        nodes: dict[int, tuple[float, float]] = {}
        ways: list[dict[str, Any]] = []

        for element in data.get("elements", []):
            if element["type"] == "node":
                nodes[element["id"]] = (element["lat"], element["lon"])
            elif element["type"] == "way":
                tags = element.get("tags", {})
                if tags.get("building") or tags.get("building:part"):
                    ways.append(element)

        buildings: list[Building] = []
        for element in ways:
            polygon = _build_polygon(element, nodes)
            if polygon is None:
                continue
            height_m, confidence = estimate_height_m(element.get("tags", {}))
            buildings.append(
                Building(
                    polygon_wgs84=polygon,
                    height_m=height_m,
                    height_confidence=confidence,
                )
            )
        return buildings[:200]