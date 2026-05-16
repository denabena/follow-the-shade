from typing import Literal

from pydantic import BaseModel, Field

ExposurePreference = Literal["sun", "shade", "either"]
TimePreset = Literal["morning", "lunch", "afternoon"]


class UserPreferences(BaseModel):
    exposure_preference: ExposurePreference = "either"
    favorite_areas: list[str] = Field(default_factory=lambda: ["Riva"])
    default_time_preset: TimePreset = "afternoon"
    digest_enabled: bool = False
    avoid_busy: bool = False


class UserPreferencesPatch(BaseModel):
    exposure_preference: ExposurePreference | None = None
    favorite_areas: list[str] | None = None
    default_time_preset: TimePreset | None = None
    digest_enabled: bool | None = None
    avoid_busy: bool | None = None
