"use client"

import { useCallback, useRef, useState } from "react"
import type { Cafe, IntentRequest } from "@/lib/types"
import { suggestions, type SuggestionId } from "@/lib/intent"
import { greet } from "@/lib/conversation"
import { createThreadId, sendFinalAnswer } from "@/lib/backend"
import {
  intentFromMapPayload,
  resultsFromMapPayload
} from "@/lib/map-payload-adapter"
import ChatPanel from "./ChatPanel"
import MapPanel, { type MapPanelHandle } from "./MapPanel"
import type { ChatMessageData } from "./ChatMessage"

type Phase =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "done"; intent: IntentRequest }

const newId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

const Studio = () => {
  const [messages, setMessages] = useState<ChatMessageData[]>([
    { id: newId(), role: "bot", text: greet(), streaming: true }
  ])
  const [phase, setPhase] = useState<Phase>({ kind: "idle" })
  const [threadId] = useState(() => createThreadId())

  const mapRef = useRef<MapPanelHandle>(null)

  const pushMessage = useCallback((m: ChatMessageData) => {
    setMessages((prev) => [...prev, m])
  }, [])

  const handleStreamComplete = useCallback((messageId: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, streaming: false } : m))
    )
  }, [])

  const beginQuery = useCallback(
    async (userUtterance: string) => {
      pushMessage({ id: newId(), role: "user", text: userUtterance })
      setPhase({ kind: "checking" })
      mapRef.current?.clearResults()
      mapRef.current?.setShadeOpacity(0)

      try {
        const response = await sendFinalAnswer({
          message: userUtterance,
          thread_id: threadId,
          include_audio: false
        })

        if (!response.map_payload) {
          pushMessage({
            id: newId(),
            role: "bot",
            text: response.answer,
            streaming: true
          })
          setPhase({ kind: "idle" })
          return
        }

        const intent = intentFromMapPayload(response.map_payload)
        const results = resultsFromMapPayload(response.map_payload)
        await mapRef.current?.flyTo(intent.area)
        mapRef.current?.setResults(results, response.map_payload.request.preference)

        pushMessage({
          id: newId(),
          role: "bot",
          text: response.answer,
          streaming: true,
          intent,
          results: { items: results, intent },
          outro: response.sources.length
            ? `Sources: ${response.sources.join(" · ")}`
            : undefined
        })
        setPhase({ kind: "done", intent })
      } catch (err) {
        const detail = err instanceof Error ? err.message : "Unknown error"
        pushMessage({
          id: newId(),
          role: "bot",
          text: `I could not reach the backend chat endpoint (${detail}). Check FOLLOW_THE_SHADE_API_BASE_URL and the backend server.`,
          streaming: true
        })
        setPhase({ kind: "idle" })
      }
    },
    [pushMessage, threadId]
  )

  const handleSuggestion = useCallback(
    (id: SuggestionId) => {
      if (phase.kind !== "idle" && phase.kind !== "done") return
      const suggestion = suggestions.find((item) => item.id === id)
      if (!suggestion) return
      beginQuery(suggestion.utterance)
    },
    [phase, beginQuery]
  )

  const handleSend = useCallback(
    (text: string) => {
      if (phase.kind !== "idle" && phase.kind !== "done") return
      beginQuery(text)
    },
    [phase, beginQuery]
  )

  const handleCafeSelect = useCallback((cafe: Cafe) => {
    mapRef.current?.focusCafe(cafe)
  }, [])

  const handleMapReady = useCallback(() => undefined, [])

  const showSuggestions =
    (phase.kind === "idle" || phase.kind === "done") &&
    messages.filter((m) => m.role === "user").length === 0

  const busy = phase.kind === "checking"

  return (
    <div className="flex h-screen w-full flex-col lg:grid lg:grid-cols-[minmax(420px,38%)_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)]">
      <div className="min-h-0 flex-1 overflow-hidden">
        <ChatPanel
          messages={messages}
          busy={busy}
          showSuggestions={showSuggestions}
          onSend={handleSend}
          onSuggestion={handleSuggestion}
          onStreamComplete={handleStreamComplete}
          onCafeSelect={handleCafeSelect}
        />
      </div>
      <div className="relative h-[45vh] shrink-0 overflow-hidden bg-bone-deep lg:h-auto">
        <MapPanel
          ref={mapRef}
          onReady={handleMapReady}
          onCafeClick={handleCafeSelect}
        />
      </div>
    </div>
  )
}

export default Studio
