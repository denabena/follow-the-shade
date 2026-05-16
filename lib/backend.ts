import type { ChatRequest, ChatResponse } from "@/lib/follow-the-shade/types";
import { answerFromMapPayload } from "@/lib/map-payload-adapter";

type FlexibleChatResponse = ChatResponse & {
  response?: unknown;
  message?: unknown;
  text?: unknown;
  detail?: unknown;
  error?: unknown;
};

export const createThreadId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `thread_${Date.now().toString(36)}_${Math.random()
    .toString(36)
    .slice(2, 10)}`;
};

export const sendFinalAnswer = async (
  request: ChatRequest,
): Promise<ChatResponse> => {
  const response = await fetch("/chat/final_answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed with ${response.status}`);
  }

  return normalizeChatResponse((await response.json()) as FlexibleChatResponse);
};

const normalizeChatResponse = (
  response: FlexibleChatResponse,
): ChatResponse => {
  const answer = firstNonEmptyString(
    response.answer,
    response.response,
    response.message,
    response.text,
    response.detail,
    response.error,
  );

  return {
    ...response,
    answer:
      answer ??
      (response.map_payload
        ? answerFromMapPayload(response.map_payload)
        : "I checked that request for Split."),
  };
};

const firstNonEmptyString = (...values: unknown[]): string | null => {
  for (const value of values) {
    if (typeof value !== "string") continue;
    const trimmed = value.trim();
    if (trimmed) return trimmed;
  }
  return null;
};
