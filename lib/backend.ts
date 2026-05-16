import type { ChatRequest, ChatResponse } from "@/lib/follow-the-shade/types"

export const createThreadId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }
  return `thread_${Date.now().toString(36)}_${Math.random()
    .toString(36)
    .slice(2, 10)}`
}

export const sendFinalAnswer = async (
  request: ChatRequest
): Promise<ChatResponse> => {
  const response = await fetch("/chat/final_answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  })

  if (!response.ok) {
    throw new Error(`Chat request failed with ${response.status}`)
  }

  return (await response.json()) as ChatResponse
}
