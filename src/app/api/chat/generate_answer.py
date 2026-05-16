from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import json_repair
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from app.api.chat.schemas import StructuredChatAnswer
from services.follow_the_shade.thread_context import current_thread_id

log = logging.getLogger(__name__)

MAX_RETRIES = 2
DEFAULT_AGENT_RECURSION_LIMIT = 40


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
