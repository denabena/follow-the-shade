from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from services.follow_the_shade.thread_context import (
    current_thread_id,
    current_user_query,
)

log = logging.getLogger(__name__)

MAX_RETRIES = 2
DEFAULT_AGENT_RECURSION_LIMIT = 40

_ENGLISH_ANSWER_COPY = {
    "preferences": {
        "sun": "sunny",
        "shade": "shade-friendly",
        "either": "outdoor",
    },
    "found": "I found {count} {preference} {options} near {location} for {window}.",
    "none": "I could not find a solid {preference} match near {location} for {window}.",
    "one": "option",
    "many": "options",
    "weather_block": "Rain or heavy cloud keeps direct sun off the terrace during that window.",
    "weather_cloud": "Cloud cover keeps the sun muted during that window.",
}


@dataclass(frozen=True)
class ChatFlowResult:
    answer: str
    analysis_id: str | None = None
    map_payload: dict[str, Any] | None = None
    sources: list[Any] = field(default_factory=list)
    detected_language: str | None = None


def _build_agent_messages(
    *,
    user_input: str,
    retry_instruction: str | None = None,
) -> list[SystemMessage | HumanMessage]:
    messages: list[SystemMessage | HumanMessage] = []
    if retry_instruction:
        messages.append(SystemMessage(content=retry_instruction))
    messages.append(HumanMessage(content=user_input))
    return messages


def normalize_map_answer(
    answer: str,
    map_payload: dict[str, Any] | None,
) -> str:
    if not isinstance(map_payload, dict):
        return answer.strip()

    request = map_payload.get("request") or {}
    results = map_payload.get("results") or []
    if not isinstance(request, dict) or not isinstance(results, list):
        return answer.strip()

    copy = _ENGLISH_ANSWER_COPY
    preferences = copy["preferences"]
    requested_preference = request.get("preference")
    weather_state = _weather_state(results)
    if requested_preference == "sun" and weather_state == "blocked":
        requested_preference = "either"
    preference = preferences.get(requested_preference, preferences["either"])
    location = request.get("location_label") or "Split"
    window = _format_window(request.get("start"), request.get("end"))
    count = len(results)

    if count == 0:
        sentences = [
            copy["none"].format(
                preference=preference,
                location=location,
                window=window,
            )
        ]
    else:
        option_word = copy["one"] if count == 1 else copy["many"]
        sentences = [
            copy["found"].format(
                count=count,
                preference=preference,
                options=option_word,
                location=location,
                window=window,
            )
        ]

    weather_sentence = _weather_sentence(weather_state, copy)
    if weather_sentence:
        sentences.append(weather_sentence)

    return " ".join(sentences).strip() or answer.strip()


def _format_window(start: Any, end: Any) -> str:
    start_label = _format_time(start)
    end_label = _format_time(end)
    if start_label and end_label:
        return f"{start_label}-{end_label}"
    return "the requested window"


def _format_time(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return None


def _weather_state(results: list[Any]) -> str | None:
    weather_values = [
        result.get("weather", {})
        for result in results
        if isinstance(result, dict) and isinstance(result.get("weather"), dict)
    ]
    precipitation_mm = _max_float(weather_values, "precipitation_mm_max")
    precipitation_probability = _max_float(
        weather_values, "precipitation_probability_max"
    )
    cloud_cover = _max_float(weather_values, "cloud_cover_avg")

    if (
        (precipitation_mm is not None and precipitation_mm > 0)
        or (precipitation_probability is not None and precipitation_probability >= 70)
        or (cloud_cover is not None and cloud_cover >= 85)
    ):
        return "blocked"
    if cloud_cover is not None and cloud_cover > 60:
        return "cloudy"
    return None


def _weather_sentence(weather_state: str | None, copy: dict[str, Any]) -> str | None:
    if weather_state == "blocked":
        return str(copy["weather_block"])
    if weather_state == "cloudy":
        return str(copy["weather_cloud"])
    return None


def _max_float(items: list[dict[str, Any]], key: str) -> float | None:
    values = []
    for item in items:
        value = item.get(key)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


async def run_chat_flow(
    *,
    input_text: str,
    thread_id: str,
    agent_app: Any,
    extra_config: dict[str, Any] | None = None,
    max_retries: int = MAX_RETRIES,
) -> ChatFlowResult:
    incoming_messages = _build_agent_messages(user_input=input_text)
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": DEFAULT_AGENT_RECURSION_LIMIT,
    }
    if extra_config:
        for key, value in extra_config.items():
            if key == "configurable" and isinstance(value, dict):
                config["configurable"].update(value)
            elif key == "recursion_limit":
                config["recursion_limit"] = value
            else:
                config["configurable"][key] = value

    thread_token = current_thread_id.set(thread_id)
    query_token = current_user_query.set(input_text)
    try:
        for attempt in range(max_retries + 1):
            try:
                response = await agent_app.ainvoke(
                    {"messages": incoming_messages}, config
                )
            except Exception as exc:
                log.error(
                    "Agent execution failed on attempt %s: %s",
                    attempt,
                    exc,
                    exc_info=True,
                )
                if attempt < max_retries:
                    incoming_messages = _build_agent_messages(
                        user_input=input_text,
                        retry_instruction=(
                            "The previous attempt failed while using a tool or generating "
                            "the answer. Retry using only the tools assigned to this agent. "
                            "If you already have a tool result, do not call the same tool again. "
                            "Return a concise English answer."
                        ),
                    )
                    continue
                return ChatFlowResult(
                    answer=(
                        "I hit an internal error while checking that request. "
                        "Try again with the same Split area and time."
                    ),
                    detected_language="en",
                )

            ai_text = (extract_ai_text(response) or "").strip()
            tool_payload = extract_tool_payload(response)
            return ChatFlowResult(
                answer=tool_payload.get("answer")
                or ai_text
                or "I checked that request for Split.",
                detected_language="en",
                analysis_id=tool_payload.get("analysis_id"),
                map_payload=tool_payload.get("map_payload"),
                sources=tool_payload.get("sources", []),
            )
    finally:
        current_user_query.reset(query_token)
        current_thread_id.reset(thread_token)

    return ChatFlowResult(
        answer="I could not process that request.", detected_language="en"
    )


def extract_ai_text(response: dict[str, Any] | None) -> str:
    if not response or "messages" not in response:
        return ""
    ai_messages = [
        message for message in response["messages"] if isinstance(message, AIMessage)
    ]
    if not ai_messages:
        return ""
    content = ai_messages[-1].content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content or "")


def extract_tool_payload(response: dict[str, Any] | None) -> dict[str, Any]:
    if not response or "messages" not in response:
        return {"analysis_id": None, "map_payload": None, "sources": []}

    for message in reversed(response["messages"]):
        if not isinstance(message, ToolMessage):
            continue
        parsed = _parse_tool_json(message.content)
        if parsed and (
            "map_payload" in parsed or "analysis_id" in parsed or parsed.get("answer")
        ):
            return {
                "answer": parsed.get("answer"),
                "analysis_id": parsed.get("analysis_id"),
                "map_payload": parsed.get("map_payload"),
                "sources": parsed.get("sources", []),
            }
    return {"analysis_id": None, "map_payload": None, "sources": []}


def _parse_tool_json(content: Any) -> dict[str, Any] | None:
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    try:
        parsed = json.loads(str(content or ""))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
