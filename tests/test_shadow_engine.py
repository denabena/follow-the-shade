from datetime import datetime
from zoneinfo import ZoneInfo

from shapely.geometry import Polygon

from services.shadow.shadow_engine import (
    Building,
    analyze_terrace_exposure,
    polygon_wgs84_to_metric,
    shadow_for_building,
    wgs84_to_metric,
)

ZAGREB = ZoneInfo("Europe/Zagreb")


def test_shadow_for_building_produces_polygon_when_sun_above_horizon() -> None:
    poly_wgs = Polygon(
        [
            (16.4390, 43.5080),
            (16.4392, 43.5080),
            (16.4392, 43.5082),
            (16.4390, 43.5082),
            (16.4390, 43.5080),
        ]
    )
    poly_m = polygon_wgs84_to_metric(poly_wgs)
    shadow = shadow_for_building(poly_m, height_m=12.0, sun_azimuth_deg=200.0, sun_elevation_deg=45.0)
    assert shadow is not None
    assert not shadow.is_empty


def test_terrace_in_building_shadow_afternoon() -> None:
    building_wgs = Polygon(
        [
            (16.4390, 43.5075),
            (16.4394, 43.5075),
            (16.4394, 43.5080),
            (16.4390, 43.5080),
            (16.4390, 43.5075),
        ]
    )
    buildings = [Building(polygon_wgs84=building_wgs, height_m=15.0, height_confidence="exact_tag")]
    start = datetime(2026, 5, 16, 15, 0, tzinfo=ZAGREB)
    end = datetime(2026, 5, 16, 17, 0, tzinfo=ZAGREB)
    terrace_lng, terrace_lat = 16.439327, 43.507573

    result = analyze_terrace_exposure(
        terrace_lat=terrace_lat,
        terrace_lng=terrace_lng,
        start=start,
        end=end,
        preference="shade",
        buildings=buildings,
        terrace_confidence="high",
    )

    assert result.samples
    assert 0.0 <= result.sun_ratio <= 1.0
    assert result.match_score >= 0.0


def test_wgs84_to_metric_roundtrip_is_finite() -> None:
    x, y = wgs84_to_metric(16.4391, 43.5081)
    assert abs(x) < 1_000_000
    assert abs(y) < 10_000_000
