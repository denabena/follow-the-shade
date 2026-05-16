from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

log = logging.getLogger(__name__)
ZAGREB_TZ = ZoneInfo("Europe/Zagreb")


class OpenMeteoClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def window_weather(
        self,
        lat: float,
        lng: float,
        start: datetime,
        end: datetime,
    ) -> dict[str, float | None]:
        start_local = start.astimezone(ZAGREB_TZ)
        end_local = end.astimezone(ZAGREB_TZ)
        params = {
            "latitude": lat,
            "longitude": lng,
            "hourly": "cloud_cover,precipitation_probability",
            "timezone": "Europe/Zagreb",
            "start_date": start_local.date().isoformat(),
            "end_date": end_local.date().isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{self.base_url}/forecast", params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            log.warning("Open-Meteo request failed: %s", exc)
            return {"cloud_cover_avg": None, "precipitation_probability_max": None}

        hourly = data.get("hourly", {})
        times: list[str] = hourly.get("time", [])
        cloud_values = hourly.get("cloud_cover", [])
        precip_values = hourly.get("precipitation_probability", [])

        selected_cloud: list[float] = []
        selected_precip: list[float] = []
        for index, time_label in enumerate(times):
            hour_dt = datetime.fromisoformat(time_label).replace(tzinfo=ZAGREB_TZ)
            if start_local <= hour_dt <= end_local:
                if index < len(cloud_values) and cloud_values[index] is not None:
                    selected_cloud.append(float(cloud_values[index]))
                if index < len(precip_values) and precip_values[index] is not None:
                    selected_precip.append(float(precip_values[index]))

        return {
            "cloud_cover_avg": round(sum(selected_cloud) / len(selected_cloud), 1)
            if selected_cloud
            else None,
            "precipitation_probability_max": max(selected_precip)
            if selected_precip
            else None,
        }
