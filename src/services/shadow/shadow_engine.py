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
    confidence: Literal["high", "medium", "low"]
    confidence_reasons: list[str]


def wgs84_to_metric(lng: float, lat: float) -> tuple[float, float]:
    x, y = _to_metric.transform(lng, lat)
    return x, y


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
    for point_1, point_2 in zip(coords, coords[1:]):
        strips.append(
            Polygon(
                [
                    point_1,
                    point_2,
                    (point_2[0] + dx, point_2[1] + dy),
                    (point_1[0] + dx, point_1[1] + dy),
                ]
            )
        )
    shadow = unary_union(strips + [shifted]).difference(poly_m)
    if shadow.is_empty:
        return None
    return shadow


def sample_times(start: datetime, end: datetime, step_minutes: int = 20) -> list[datetime]:
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
        (polygon_wgs84_to_metric(building.polygon_wgs84), building.height_m)
        for building in buildings
    ]
    terrace_x, terrace_y = wgs84_to_metric(terrace_lng, terrace_lat)
    terrace_point = Point(terrace_x, terrace_y)

    samples: list[ExposureSample] = []
    for when in times:
        sun = sun_at(terrace_lat, terrace_lng, when)
        if sun.elevation_deg <= 0:
            samples.append(ExposureSample(time=when, state="shade"))
            continue

        shadows = []
        for poly_m, height_m in building_polys_m:
            shadow = shadow_for_building(
                poly_m,
                height_m,
                sun.azimuth_deg,
                sun.elevation_deg,
            )
            if shadow is not None:
                shadows.append(shadow)

        if shadows:
            shadow_union = unary_union(shadows)
            in_shadow = shadow_union.contains(terrace_point) or shadow_union.touches(
                terrace_point
            )
            state: ExposureState = "shade" if in_shadow else "sun"
        else:
            state = "sun"
        samples.append(ExposureSample(time=when, state=state))

    sun_count = sum(1 for sample in samples if sample.state == "sun")
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

    confidence: Literal["high", "medium", "low"] = "medium"
    confidence_reasons = []
    if terrace_confidence == "low":
        confidence = "low"
        confidence_reasons.append("terrace point estimated")
    if height_estimates_used:
        confidence_reasons.append("building heights partly estimated")
    if not buildings:
        confidence = "low"
        confidence_reasons.append("limited building geometry nearby")
    if not confidence_reasons:
        confidence = "high"
        confidence_reasons.append("building-shadow analysis")

    return ExposureResult(
        samples=samples,
        sun_ratio=round(sun_ratio, 2),
        match_score=round(match_score, 2),
        summary=_summarize(samples),
        transition_notes=transition_notes,
        confidence=confidence,
        confidence_reasons=confidence_reasons,
    )


def _summarize(samples: list[ExposureSample]) -> str:
    sun_count = sum(1 for sample in samples if sample.state == "sun")
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
    haversine = sin(d_lat / 2) ** 2 + cos(lat_1) * cos(lat_2) * sin(d_lng / 2) ** 2
    return 2 * radius * asin(sqrt(haversine))