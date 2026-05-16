from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings copied from the AI backend shape."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    GOOGLE_PLACES_API_KEY: Optional[str] = None
    FOURSQUARE_API_KEY: Optional[str] = None
    OUTSCRAPER_API_KEY: Optional[str] = None
    SHADOWMAP_API_KEY: Optional[str] = None
    SHADEMAP_API_KEY: Optional[str] = None
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"

    SONIOX_API_KEY: Optional[str] = None
    SONIOX_API_KEY_TTS: Optional[str] = None
    SONIOX_AUTH_BASE_URL: str = "https://api.soniox.com/v1"
    SONIOX_API_HOST_TTS: str = "https://tts-rt.soniox.com/tts"
    SONIOX_STT_MODEL: str = "stt-rt-v4"
    SONIOX_STT_LANGUAGE_HINTS: str = "hr,en,it,de,sl,fr"
    SONIOX_STT_TEMP_KEY_EXPIRES_SECONDS: int = 300
    SONIOX_STT_MAX_ENDPOINT_DELAY_MS: int = 900
    SONIOX_TTS_MODEL: str = "tts-rt-v1"
    SONIOX_TTS_LANGUAGE: str = "en"
    SONIOX_TTS_VOICE: str = "Grace"
    SONIOX_TTS_AUDIO_FORMAT: str = "mp3"
    SONIOX_TTS_STREAM_AUDIO_FORMAT: str = "pcm_s16le"
    SONIOX_TTS_STREAM_SAMPLE_RATE: int = 24000
    SONIOX_TTS_TIMEOUT_SECONDS: float = 30.0

    SESSION_TTL_SECONDS: int = 24 * 60 * 60
    SPLIT_CAFE_SEED_PATH: str = "assets/split_cafe_seed.json"
    CHAT_MAX_INPUT_CHARS: int = 800
    FOLLOW_THE_SHADE_DATA_MODE: Literal["mock", "actual"] = "mock"
    FOLLOW_THE_SHADE_CACHE_TTL_SECONDS: int = 10 * 60

    LOG_LEVEL: str = "INFO"
    ACCEPT_LOG_LEVEL: str = "INFO"

    CLERK_ISSUER: Optional[str] = None
    CLERK_JWKS_URL: Optional[str] = None
    CLERK_JWT_PUBLIC_KEY: Optional[str] = None
    USER_PREFERENCES_PATH: str = "data/user_preferences.json"

    @property
    def clerk_jwks_url(self) -> str | None:
        if self.CLERK_JWKS_URL:
            return self.CLERK_JWKS_URL
        if self.CLERK_ISSUER:
            return f"{self.CLERK_ISSUER.rstrip('/')}/.well-known/jwks.json"
        return None


settings = Settings()
