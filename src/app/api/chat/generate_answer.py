from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import json_repair
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from app.api.chat.schemas import StructuredChatAnswer
from services.follow_the_shade.thread_context import current_thread_id

log = logging.getLogger(__name__)

MAX_RETRIES = 2
DEFAULT_AGENT_RECURSION_LIMIT = 40

_ANSWER_COPY = {
    "en": {
        "preferences": {
            "sun": "sunny",
            "shade": "shade-friendly",
            "either": "outdoor",
        },
        "found": "I found {count} {preference} {options} near {location} for {window}.",
        "none": "I could not find a solid {preference} match near {location} for {window}.",
        "one": "option",
        "many": "options",
        "weather_block": "Open-Meteo shows rain or heavy cloud, so direct sun is not expected.",
        "weather_cloud": "Cloud cover is high, so direct sun may feel weaker than the geometric shade model.",
        "uncertainty": "Some terrace points or building heights are estimated, so treat the timing as approximate.",
    },
    "hr": {
        "preferences": {"sun": "suncanih", "shade": "sjenovitih", "either": "vanjskih"},
        "found": "Pronasao sam {count} {preference} opcija blizu {location} za {window}.",
        "none": "Nisam nasao pouzdanu {preference} opciju blizu {location} za {window}.",
        "one": "opcija",
        "many": "opcija",
        "weather_block": "Open-Meteo pokazuje kisu ili gustu naoblaku, pa izravno sunce nije ocekivano.",
        "weather_cloud": "Naoblaka je visoka, pa ce izravno sunce biti slabije od same geometrije.",
        "uncertainty": "Neke terase ili visine zgrada su procijenjene, pa vrijeme sjene uzmi kao priblizno.",
    },
    "it": {
        "preferences": {"sun": "al sole", "shade": "all'ombra", "either": "all'aperto"},
        "found": "Ho trovato {count} opzioni {preference} vicino a {location} per {window}.",
        "none": "Non ho trovato una buona opzione {preference} vicino a {location} per {window}.",
        "one": "opzione",
        "many": "opzioni",
        "weather_block": "Open-Meteo indica pioggia o molte nuvole, quindi il sole diretto non e previsto.",
        "weather_cloud": "La copertura nuvolosa e alta, quindi il sole diretto puo sembrare piu debole del modello geometrico.",
        "uncertainty": "Alcuni punti terrazza o altezze degli edifici sono stimati, quindi gli orari sono approssimativi.",
    },
    "de": {
        "preferences": {"sun": "sonnige", "shade": "schattige", "either": "Outdoor-"},
        "found": "Ich habe {count} {preference} Optionen nahe {location} fuer {window} gefunden.",
        "none": "Ich habe keine solide {preference} Option nahe {location} fuer {window} gefunden.",
        "one": "Option",
        "many": "Optionen",
        "weather_block": "Open-Meteo zeigt Regen oder dichte Bewoelkung, daher ist keine direkte Sonne zu erwarten.",
        "weather_cloud": "Die Bewoelkung ist hoch, daher kann direkte Sonne schwaecher wirken als im geometrischen Modell.",
        "uncertainty": "Einige Terrassenpunkte oder Gebaeudehoehen sind geschaetzt, daher sind die Zeiten ungefaehr.",
    },
    "sl": {
        "preferences": {"sun": "soncnih", "shade": "sencnih", "either": "zunanjih"},
        "found": "Nasel sem {count} {preference} moznosti blizu {location} za {window}.",
        "none": "Nisem nasel zanesljive {preference} moznosti blizu {location} za {window}.",
        "one": "moznost",
        "many": "moznosti",
        "weather_block": "Open-Meteo kaze dez ali gosto oblacnost, zato neposrednega sonca ni pricakovati.",
        "weather_cloud": "Oblacnost je visoka, zato je neposredno sonce lahko sibkejse od geometrijskega modela.",
        "uncertainty": "Nekatere terase ali visine stavb so ocenjene, zato so casi priblizni.",
    },
    "fr": {
        "preferences": {
            "sun": "ensoleillees",
            "shade": "ombragees",
            "either": "en terrasse",
        },
        "found": "J'ai trouve {count} options {preference} pres de {location} pour {window}.",
        "none": "Je n'ai pas trouve de bonne option {preference} pres de {location} pour {window}.",
        "one": "option",
        "many": "options",
        "weather_block": "Open-Meteo indique de la pluie ou une forte couverture nuageuse, donc le soleil direct n'est pas attendu.",
        "weather_cloud": "La couverture nuageuse est elevee, donc le soleil direct peut sembler plus faible que dans le modele geometrique.",
        "uncertainty": "Certains points de terrasse ou hauteurs de batiments sont estimes, donc les horaires restent approximatifs.",
    },
}


@dataclass(frozen=True)
class ChatFlowResult:
    answer: str
    analysis_id: str | None = None
    map_payload: dict[str, Any] | None = None
    sources: list[Any] = field(default_factory=list)
    detected_language: str | None = None


def _strip_json_fence(output_text: str) -> str:
    text = output_text.strip()
    match = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else text


def parse_structured_chat_answer(output_text: str) -> StructuredChatAnswer:
    if not output_text.strip():
        raise ValueError("Agent returned an empty final answer.")
    try:
        repaired_json = json_repair.loads(_strip_json_fence(output_text))
    except Exception as exc:
        raise ValueError(f"Failed to parse structured agent answer: {exc}") from exc
    try:
        return StructuredChatAnswer.model_validate(repaired_json)
    except ValidationError as exc:
        raise ValueError(f"Structured agent answer failed validation: {exc}") from exc


def extract_structured_chat_answer(
    response: dict[str, Any] | None,
) -> StructuredChatAnswer | None:
    if not response:
        return None
    structured_response = response.get("structured_response")
    if structured_response is None:
        return None
    if isinstance(structured_response, StructuredChatAnswer):
        return structured_response
    return StructuredChatAnswer.model_validate(structured_response)


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
    detected_language: str | None = None,
) -> str:
    if not isinstance(map_payload, dict):
        return answer.strip()

    request = map_payload.get("request") or {}
    results = map_payload.get("results") or []
    if not isinstance(request, dict) or not isinstance(results, list):
        return answer.strip()

    language = detected_language if detected_language in _ANSWER_COPY else "en"
    copy = _ANSWER_COPY[language]
    preferences = copy["preferences"]
    preference = preferences.get(request.get("preference"), preferences["either"])
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

    weather_sentence = _weather_sentence(results, copy)
    if weather_sentence:
        sentences.append(weather_sentence)
    if _has_estimated_geometry(map_payload):
        sentences.append(copy["uncertainty"])

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


def _weather_sentence(results: list[Any], copy: dict[str, Any]) -> str | None:
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
        return str(copy["weather_block"])
    if cloud_cover is not None and cloud_cover > 60:
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


def _has_estimated_geometry(map_payload: dict[str, Any]) -> bool:
    text_parts = list(map(str, map_payload.get("source_notes") or []))
    for result in map_payload.get("results") or []:
        if not isinstance(result, dict):
            continue
        exposure = result.get("exposure") or {}
        if isinstance(exposure, dict):
            text_parts.extend(map(str, exposure.get("confidence_reasons") or []))
    combined = " ".join(text_parts).lower()
    return any(
        token in combined
        for token in (
            "estimated",
            "missing building",
            "default height",
            "approx",
            "fallback",
        )
    )


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

    token = current_thread_id.set(thread_id)
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
                            "Return only the required JSON object."
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

            ai_text = extract_ai_text(response) or ""
            try:
                structured_answer = extract_structured_chat_answer(response)
                if structured_answer is None:
                    structured_answer = parse_structured_chat_answer(ai_text)
            except ValueError as exc:
                log.error(
                    "Agent returned invalid structured output on attempt %s: %s",
                    attempt,
                    exc,
                )
                if attempt < max_retries:
                    incoming_messages = _build_agent_messages(
                        user_input=input_text,
                        retry_instruction=(
                            "Your previous final output was not valid structured JSON. "
                            "Return only a JSON object with exactly `response` and "
                            "`detected_language`. Do not call the same tool again if the "
                            "history already contains its result."
                        ),
                    )
                    continue
                return ChatFlowResult(
                    answer="I could not format the answer cleanly. Please try again.",
                    detected_language="en",
                )

            tool_payload = extract_tool_payload(response)
            return ChatFlowResult(
                answer=structured_answer.response.strip(),
                detected_language=structured_answer.detected_language,
                analysis_id=tool_payload.get("analysis_id"),
                map_payload=tool_payload.get("map_payload"),
                sources=tool_payload.get("sources", []),
            )
    finally:
        current_thread_id.reset(token)

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
