"use client"

import { useEffect, useRef, useState } from "react"
import type { Cafe } from "@/lib/types"
import { cn } from "@/lib/cn"
import { suggestions, type SuggestionId } from "@/lib/intent"
import ChatMessage, { type ChatMessageData } from "./ChatMessage"

type Props = {
  messages: ChatMessageData[]
  busy: boolean
  showSuggestions: boolean
  onSend: (text: string) => void
  onSuggestion: (id: SuggestionId) => void
  onStreamComplete: (messageId: string) => void
  onCafeSelect: (cafe: Cafe) => void
}

const ChatPanel = ({
  messages,
  busy,
  showSuggestions,
  onSend,
  onSuggestion,
  onStreamComplete,
  onCafeSelect
}: Props) => {
  const [draft, setDraft] = useState("")
  const scrollerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  }, [messages])

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const trimmed = draft.trim()
    if (!trimmed || busy) return
    setDraft("")
    onSend(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      const trimmed = draft.trim()
      if (!trimmed || busy) return
      setDraft("")
      onSend(trimmed)
    }
  }

  return (
    <section
      aria-label="Conversation"
      className="grain relative flex h-full min-h-0 flex-col border-r border-ink/10 bg-bone"
    >
      <Header />

      <div
        ref={scrollerRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        className="relative z-[2] flex-1 space-y-6 overflow-y-auto px-7 pb-6 pt-2 sm:px-10"
      >
        {messages.map((m) => (
          <ChatMessage
            key={m.id}
            message={m}
            onStreamComplete={() => onStreamComplete(m.id)}
            onCafeSelect={onCafeSelect}
          />
        ))}
      </div>

      {showSuggestions && (
        <div className="relative z-[2] flex flex-wrap gap-2 border-t border-ink/8 px-7 py-4 sm:px-10">
          {suggestions.map((s) => (
            <button
              key={s.id}
              type="button"
              aria-label={`Send suggestion: ${s.utterance}`}
              onClick={() => onSuggestion(s.id)}
              disabled={busy}
              className={cn(
                "group rounded-full border border-terracotta/40 bg-bone-soft px-3.5 py-2 text-[12.5px] leading-tight text-ink",
                "transition-all hover:-translate-y-0.5 hover:border-terracotta hover:bg-bone-deep",
                "disabled:cursor-not-allowed disabled:opacity-50"
              )}
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-terracotta-deep">
                try
              </span>
              <span className="ml-2 italic">&ldquo;{s.utterance}&rdquo;</span>
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="relative z-[2] flex items-end gap-3 border-t border-ink/10 bg-bone px-7 py-4 sm:px-10"
      >
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={busy}
          placeholder={
            busy
              ? "checking shadows…"
              : "tell me where & when, and whether you want sun or shade"
          }
          aria-label="Message"
          className={cn(
            "min-h-[44px] max-h-32 flex-1 resize-none bg-transparent text-[15px] leading-snug text-ink outline-none placeholder:text-ink/35",
            "disabled:opacity-60"
          )}
        />
        <button
          type="submit"
          disabled={!draft.trim() || busy}
          aria-label="Send message"
          className={cn(
            "shrink-0 rounded-full border border-ink px-5 py-2 text-[12.5px] font-medium uppercase tracking-[0.16em] text-ink",
            "transition-all hover:bg-ink hover:text-bone",
            "disabled:cursor-not-allowed disabled:border-ink/30 disabled:text-ink/30 disabled:hover:bg-transparent"
          )}
        >
          ask
        </button>
      </form>
    </section>
  )
}

const Header = () => (
  <header className="relative z-[2] flex items-baseline justify-between gap-4 px-7 pb-3 pt-7 sm:px-10">
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.32em] text-terracotta-deep">
        Split · sun &amp; shade
      </p>
      <h1 className="font-display text-[34px] leading-[1.05] tracking-tight text-ink">
        Follow the Shade
      </h1>
    </div>
  </header>
)

export default ChatPanel
