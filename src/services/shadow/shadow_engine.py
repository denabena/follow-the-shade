from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt, tan
from typing import Literal

from pyproj import Transformer
from shapely import affinity
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from services.shadow.sun_position import sun_at

ExposureState = Literal["sun", "shade"]
METRIC_CRS = "EPSG:32633"
WGS84 = "EPSG:4326"
_to_metric = Transformer.from_crs(WGS84, METRIC_CRS, always_xy=True)
_to_wgs84 = Transformer.from_crs(METRIC_CRS, WGS84, always_xy=True)


@dataclass(frozen=True)
class Building:
    polygon_wgs84: Polygon
    height_m: float
    height_confidence: str


@dataclass(frozen=True)
class ExposureSample:
    time: datetime
    state: ExposureState


@dataclass(frozen=True)
class ExposureResult:
    samples: list[ExposureSample]
    sun_ratio: float
    match_score: float
    summary: str
    transition_notes: list[str]
    confidence: str
    confidence_reasons: list[str]


def wgs84_to_metric(lng: float, lat: float) -> tuple[float, float]:
    x, y = _to_metric.transform(lng, lat)
    return x, y


def metric_to_wgs84(x: float, y: float) -> tuple[float, float]:
    lng, lat = _to_wgs84.transform(x, y)
    return lng, lat


def polygon_wgs84_to_metric(polygon: Polygon) -> Polygon:
    coords = [wgs84_to_metric(lng, lat) for lng, lat in polygon.exterior.coords]
    return Polygon(coords)


def shadow_for_building(
    poly_m: Polygon,
    height_m: float,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
) -> Polygon | None:
    if sun_elevation_deg <= 0 or height_m <= 0:
        return None

    length = height_m / tan(radians(sun_elevation_deg))
    shadow_azimuth = radians((sun_azimuth_deg + 180.0) % 360.0)
    dx = length * sin(shadow_azimuth)
    dy = length * cos(shadow_azimuth)

    shifted = affinity.translate(poly_m, xoff=dx, yoff=dy)
    coords = list(poly_m.exterior.coords)
    strips: list[Polygon] = []
    for p1, p2 in zip(coords, coords[1:]):
        strips.append(
            Polygon([p1, p2, (p2[0] + dx, p2[1] + dy), (p1[0] + dx, p1[1] + dy)])
        )
    shadow = unary_union(strips + [shifted]).difference(poly_m)
    if shadow.is_empty:
        return None
    return shadow


def sample_times(
    start: datetime, end: datetime, step_minutes: int = 20
) -> list[datetime]:
    if end <= start:
        return [start]
    samples = []
    current = start
    step = timedelta(minutes=step_minutes)
    while current <= end:
        samples.append(current)
        current += step
    if samples[-1] != end:
        samples.append(end)
    return samples


def analyze_terrace_exposure(
    *,
    terrace_lat: float,
    terrace_lng: float,
    start: datetime,
    end: datetime,
    preference: Literal["sun", "shade", "either"],
    buildings: list[Building],
    terrace_confidence: str = "medium",
    height_estimates_used: bool = False,
    step_minutes: int = 20,
) -> ExposureResult:
    times = sample_times(start, end, step_minutes=step_minutes)
    building_polys_m = [
        (polygon_wgs84_to_metric(b.polygon_wgs84), b.height_m) for b in buildings
    ]
    tx, ty = wgs84_to_metric(terrace_lng, terrace_lat)
    terrace_point = Point(tx, ty)

    samples: list[ExposureSample] = []
    for when in times:
        sun = sun_at(terrace_lat, terrace_lng, when)
        if sun.elevation_deg <= 0:
            samples.append(ExposureSample(time=when, state="shade"))
            continue

        state: ExposureState = "sun"
        for poly_m, height_m in building_polys_m:
            shadow_length_m = height_m / tan(radians(sun.elevation_deg))
            if poly_m.distance(terrace_point) > shadow_length_m + 2.0:
                continue

            shadow = shadow_for_building(
                poly_m, height_m, sun.azimuth_deg, sun.elevation_deg
            )
            if shadow is not None and (
                shadow.contains(terrace_point) or shadow.touches(terrace_point)
            ):
                state = "shade"
                break

        samples.append(ExposureSample(time=when, state=state))

    sun_count = sum(1 for s in samples if s.state == "sun")
    sun_ratio = sun_count / len(samples) if samples else 0.0

    if preference == "sun":
        match_score = sun_ratio
    elif preference == "shade":
        match_score = 1.0 - sun_ratio
    else:
        match_score = 0.72 + min(sun_ratio, 1.0 - sun_ratio) * 0.20

    transition_notes = []
    for index in range(1, len(samples)):
        if samples[index - 1].state != samples[index].state:
            transition_notes.append(
                f"{samples[index].state} around {samples[index].time.strftime('%H:%M')}"
            )

    summary = _summarize(samples)
    confidence = "low" if terrace_confidence == "low" else "medium"
    reasons = []
    if terrace_confidence == "low":
        reasons.append("terrace point estimated")
    if height_estimates_used:
        reasons.append("building heights partly estimated")
    if not buildings:
        reasons.append("limited building geometry nearby")
        confidence = "low"
    if not reasons:
        reasons.append("building-shadow analysis")

    return ExposureResult(
        samples=samples,
        sun_ratio=round(sun_ratio, 2),
        match_score=round(match_score, 2),
        summary=summary,
        transition_notes=transition_notes,
        confidence=confidence,
        confidence_reasons=reasons,
    )


def _summarize(samples: list[ExposureSample]) -> str:
    sun_count = sum(1 for s in samples if s.state == "sun")
    shade_count = len(samples) - sun_count
    start = samples[0].time.strftime("%H:%M")
    end = samples[-1].time.strftime("%H:%M")
    if shade_count == len(samples):
        return f"Mostly shaded from {start} to {end}."
    if sun_count == len(samples):
        return f"Mostly sunny from {start} to {end}."
    if shade_count > sun_count:
        return f"Mostly shaded from {start} to {end}, with a short sunny patch."
    return f"Mostly sunny from {start} to {end}, with a short shaded patch."


def haversine_m(a: dict[str, float], b: dict[str, float]) -> float:
    radius = 6371000.0
    d_lat = radians(b["lat"] - a["lat"])
    d_lng = radians(b["lng"] - a["lng"])
    lat_1 = radians(a["lat"])
    lat_2 = radians(b["lat"])
    h = sin(d_lat / 2) ** 2 + cos(lat_1) * cos(lat_2) * sin(d_lng / 2) ** 2
    return 2 * radius * asin(sqrt(h))
