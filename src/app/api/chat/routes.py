from __future__ import annotations

import base64
import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.chat.schemas import (
    AnalysisResponse,
    ChatAudio,
    ChatRequest,
    ChatResponse,
    SpeechRealtimeConfig,
    SpeechTemporaryKeyRequest,
    SpeechTemporaryKeyResponse,
    SpeechTtsRealtimeConfig,
    SpeechTtsTemporaryKeyRequest,
    SpeechTtsTemporaryKeyResponse,
)
from app.api.chat.generate_answer import (
    normalize_map_answer,
    run_chat_flow,
)
from app.auth.deps import get_optional_user_id
from app.state import AppState, get_state
from core.config import settings
from services.follow_the_shade.thread_context import current_user_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

SONIOX_LANGUAGE = "en"

SONIOX_CONTEXT_TERMS = [
    "Follow the Shade",
    "Split",
    "Riva",
    "Bacvice",
    "Marmontova",
    "Diocletian Palace",
    "Pjaca",
    "Prokurative",
    "Matejuska",
    "Varos",
    "Firule",
    "Znjan",
    "shade",
    "sunny terrace",
    "outdoor seating",
]


def _split_csv_setting(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return min(max(value, minimum), maximum)


def _build_soniox_stt_config() -> SpeechRealtimeConfig:
    return SpeechRealtimeConfig(
        model=settings.SONIOX_STT_MODEL,
        language_hints=_split_csv_setting(settings.SONIOX_STT_LANGUAGE_HINTS),
        enable_endpoint_detection=True,
        max_endpoint_delay_ms=_clamp(
            settings.SONIOX_STT_MAX_ENDPOINT_DELAY_MS,
            500,
            3000,
        ),
        context={
            "terms": SONIOX_CONTEXT_TERMS,
            "general": [
                {
                    "key": "domain",
                    "value": "Split cafes, terrace sun, building shade, tourist requests",
                }
            ],
        },
    )


def _normalise_tts_language(_language: str | None = None) -> str:
    return SONIOX_LANGUAGE


def _normalise_tts_model(model: str | None = None) -> str:
    configured_model = (model or settings.SONIOX_TTS_MODEL or "tts-rt-v1").strip()
    if configured_model == "tts-rt-preview":
        return "tts-rt-v1"
    return configured_model or "tts-rt-v1"


def _build_soniox_tts_config() -> SpeechTtsRealtimeConfig:
    return SpeechTtsRealtimeConfig(
        model=_normalise_tts_model(),
        language=_normalise_tts_language(),
        voice=settings.SONIOX_TTS_VOICE,
        audio_format=settings.SONIOX_TTS_STREAM_AUDIO_FORMAT,
        sample_rate=settings.SONIOX_TTS_STREAM_SAMPLE_RATE,
    )


async def _create_soniox_temporary_key(
    usage_type: str,
    client_reference_id: str | None = None,
) -> dict[str, Any]:
    if not settings.SONIOX_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Soniox API key is not configured.",
        )

    ttl_seconds = _clamp(settings.SONIOX_STT_TEMP_KEY_EXPIRES_SECONDS, 1, 3600)
    payload: dict[str, Any] = {
        "usage_type": usage_type,
        "expires_in_seconds": ttl_seconds,
    }
    if client_reference_id:
        payload["client_reference_id"] = client_reference_id[:256]

    url = f"{settings.SONIOX_AUTH_BASE_URL.rstrip('/')}/auth/temporary-api-key"
    headers = {"Authorization": f"Bearer {settings.SONIOX_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("Soniox temporary key request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not create a temporary Soniox key.",
        ) from exc

    if response.status_code != 201:
        log.warning(
            "Soniox temporary key request returned status %s",
            response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Could not create a temporary Soniox key.",
        )

    data = response.json()
    if not data.get("api_key") or not data.get("expires_at"):
        raise HTTPException(
            status_code=502,
            detail="Soniox temporary key response was incomplete.",
        )

    return data


def _audio_mime_type(audio_format: str) -> str:
    format_to_mime = {
        "aac": "audio/aac",
        "flac": "audio/flac",
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "wav": "audio/wav",
    }
    return format_to_mime.get(audio_format.lower(), "audio/pcm")


def _clean_tts_text(text: str) -> str:
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    cleaned = re.sub(r"\s*\[\d+\]", "", cleaned)
    cleaned = re.sub(r"[*_`#>]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:5000]


def _soniox_tts_url() -> str:
    base_url = settings.SONIOX_API_HOST_TTS.strip().rstrip("/")
    if not base_url:
        return "https://tts-rt.soniox.com/tts"
    if base_url.startswith("wss://"):
        base_url = f"https://{base_url.removeprefix('wss://')}"
    if base_url.endswith("/tts-websocket"):
        return f"{base_url.removesuffix('/tts-websocket')}/tts"
    if base_url.endswith("/tts"):
        return base_url
    return f"{base_url}/tts"


async def _generate_soniox_tts(
    answer: str,
    language: str | None = None,
) -> ChatAudio | None:
    api_key = settings.SONIOX_API_KEY_TTS or settings.SONIOX_API_KEY
    if not api_key:
        log.info("Skipping Soniox TTS because no TTS API key is configured.")
        return None

    text = _clean_tts_text(answer)
    if not text:
        return None

    audio_format = settings.SONIOX_TTS_AUDIO_FORMAT
    payload = {
        "model": _normalise_tts_model(),
        "language": _normalise_tts_language(language),
        "voice": settings.SONIOX_TTS_VOICE,
        "audio_format": audio_format,
        "text": text,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(
            timeout=settings.SONIOX_TTS_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(
                _soniox_tts_url(),
                json=payload,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        log.warning("Soniox TTS request failed: %s", exc)
        return None

    if response.status_code != 200 or not response.content:
        log.warning("Soniox TTS request returned status %s", response.status_code)
        return None

    content_type = response.headers.get("content-type") or _audio_mime_type(
        audio_format
    )
    return ChatAudio(
        mime_type=content_type.split(";", 1)[0],
        data=base64.b64encode(response.content).decode("ascii"),
    )


@router.post("/speech/stt-key", response_model=SpeechTemporaryKeyResponse)
async def create_soniox_stt_key(
    request: SpeechTemporaryKeyRequest,
) -> SpeechTemporaryKeyResponse:
    key_data = await _create_soniox_temporary_key(
        usage_type="transcribe_websocket",
        client_reference_id=request.client_reference_id,
    )
    return SpeechTemporaryKeyResponse(
        api_key=key_data["api_key"],
        expires_at=key_data["expires_at"],
        stt=_build_soniox_stt_config(),
    )


@router.post("/speech/tts-key", response_model=SpeechTtsTemporaryKeyResponse)
async def create_soniox_tts_key(
    request: SpeechTtsTemporaryKeyRequest,
) -> SpeechTtsTemporaryKeyResponse:
    key_data = await _create_soniox_temporary_key(
        usage_type="tts_rt",
        client_reference_id=request.client_reference_id,
    )
    return SpeechTtsTemporaryKeyResponse(
        api_key=key_data["api_key"],
        expires_at=key_data["expires_at"],
        tts=_build_soniox_tts_config(),
    )


_DEFAULT_AGENT_NAME = "Agent_FollowTheShade"
_ORCHESTRATOR_AGENT_NAME = "Agent_FollowTheShadeOrchestrator"


def _select_agent(message: str, state: AppState, user_id: str | None) -> str:
    """Use the LLM orchestrator for chat turns; fall back only if parsing is unavailable."""
    if state.analysis_tool is None:
        return _DEFAULT_AGENT_NAME
    return _ORCHESTRATOR_AGENT_NAME


@router.post("/final_answer", response_model=ChatResponse)
async def chat_final_answer(
    chat_request: ChatRequest,
    state: AppState = Depends(get_state),
    user_id: str | None = Depends(get_optional_user_id),
) -> ChatResponse:
    message = chat_request.text
    if state.agent_app is None:
        raise HTTPException(
            status_code=503,
            detail="The Follow the Shade chat agent is not initialized.",
        )

    active_agent = _select_agent(message, state, user_id)
    user_id_token = current_user_id.set(user_id)
    try:
        result = await run_chat_flow(
            input_text=message,
            thread_id=chat_request.thread_id,
            agent_app=state.agent_app,
            active_agent=active_agent,
        )
    finally:
        current_user_id.reset(user_id_token)

    answer = result.answer.strip() or normalize_map_answer("", result.map_payload)

    audio = None
    if chat_request.include_audio:
        audio = await _generate_soniox_tts(
            answer=answer,
            language=SONIOX_LANGUAGE,
        )

    return ChatResponse(
        answer=answer,
        thread_id=chat_request.thread_id,
        analysis_id=result.analysis_id,
        map_payload=result.map_payload,
        sources=result.sources,
        audio=audio,
        detected_language=SONIOX_LANGUAGE,
    )


@router.get("/analysis/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str,
    state: AppState = Depends(get_state),
) -> AnalysisResponse:
    record = state.analysis_store.get(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return AnalysisResponse.model_validate(record.to_dict())
