from typing import Any

from pydantic import BaseModel, Field, model_validator


class ChatAudio(BaseModel):
    mime_type: str
    data: str


class ChatRequest(BaseModel):
    message: str | None = None
    query: str | None = None
    thread_id: str = "1"
    include_audio: bool = False

    @model_validator(mode="after")
    def require_message_or_query(self) -> "ChatRequest":
        if not self.text:
            raise ValueError("message or query is required")
        return self

    @property
    def text(self) -> str:
        return (self.message or self.query or "").strip()


class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    analysis_id: str | None = None
    map_payload: dict[str, Any] | None = None
    requires_approval: bool = False
    pending_actions: list[dict[str, Any]] | None = None
    review_configs: list[dict[str, Any]] | None = None
    sources: list[Any] = Field(default_factory=list)
    audio: ChatAudio | None = None
    detected_language: str | None = None


class AnalysisResponse(BaseModel):
    analysis_id: str
    thread_id: str
    created_at: str
    expires_at: str
    query: str
    parsed_request: dict[str, Any]
    map_payload: dict[str, Any]


class SpeechTemporaryKeyRequest(BaseModel):
    client_reference_id: str | None = None


class SpeechRealtimeConfig(BaseModel):
    model: str
    language_hints: list[str] = Field(default_factory=list)
    enable_endpoint_detection: bool = True
    max_endpoint_delay_ms: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class SpeechTemporaryKeyResponse(BaseModel):
    api_key: str
    expires_at: str
    stt: SpeechRealtimeConfig


class SpeechTtsTemporaryKeyRequest(BaseModel):
    client_reference_id: str | None = None
    language: str | None = None


class SpeechTtsRealtimeConfig(BaseModel):
    model: str
    language: str
    voice: str
    audio_format: str
    sample_rate: int


class SpeechTtsTemporaryKeyResponse(BaseModel):
    api_key: str
    expires_at: str
    tts: SpeechTtsRealtimeConfig
