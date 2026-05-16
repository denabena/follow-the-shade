from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

ExposurePreference = Literal["sun", "shade", "either"]
TimePreset = Literal["morning", "lunch", "afternoon"]


class NotificationSchedule(BaseModel):
    enabled: bool = False
    email: EmailStr | None = None
    days_of_week: list[int] = Field(default_factory=lambda: [5], min_length=1)
    send_time_local: str = "12:00"
    timezone: str = "Europe/Zagreb"
    area: str = Field(default="Riva", min_length=1, max_length=80)
    time_window_preset: TimePreset = "afternoon"
    exposure_preference: ExposurePreference = "shade"
    last_sent_at_utc: str | None = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, value: list[int]) -> list[int]:
        days = sorted(set(value))
        if not days or any(day < 0 or day > 6 for day in days):
            raise ValueError("days_of_week must contain values from 0 to 6")
        return days

    @field_validator("send_time_local")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if not re.fullmatch(r"\d{2}:\d{2}", value):
            raise ValueError("send_time_local must use HH:MM")
        hour, minute = (int(part) for part in value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("send_time_local must be a valid local time")
        return value


class NotificationScheduleUpsert(BaseModel):
    enabled: bool | None = None
    email: EmailStr | None = None
    days_of_week: list[int] | None = Field(default=None, min_length=1)
    send_time_local: str | None = None
    timezone: str | None = None
    area: str | None = Field(default=None, min_length=1, max_length=80)
    time_window_preset: TimePreset | None = None
    exposure_preference: ExposurePreference | None = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        days = sorted(set(value))
        if not days or any(day < 0 or day > 6 for day in days):
            raise ValueError("days_of_week must contain values from 0 to 6")
        return days

    @field_validator("send_time_local")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return NotificationSchedule.validate_time(value)


class NotificationTestSendResponse(BaseModel):
    sent: bool
    analysis_id: str | None = None
    subject: str | None = None
    detail: str | None = None
