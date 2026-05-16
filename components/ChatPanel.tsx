"use client"

import { useAuth } from "@clerk/nextjs"
import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import type { Cafe } from "@/lib/types"
import { cn } from "@/lib/cn"
import { suggestions, type SuggestionId } from "@/lib/intent"
import ChatMessage, { type ChatMessageData } from "./ChatMessage"

type SpeechRecognitionResult = {
  isFinal: boolean
  0: { transcript: string }
}

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  abort: () => void
  onstart: (() => void) | null
  onend: (() => void) | null
  onerror: ((event: { error: string }) => void) | null
  onresult:
    | ((event: {
        resultIndex: number
        results: ArrayLike<SpeechRecognitionResult>
      }) => void)
    | null
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
}

type Props = {
  messages: ChatMessageData[]
  busy: boolean
  showSuggestions: boolean
  className?: string
  focused?: boolean
  onSend: (text: string) => void
  onSuggestion: (id: SuggestionId) => void
  onStreamComplete: (messageId: string) => void
  onCafeSelect: (cafe: Cafe) => void
}

const ChatPanel = ({
  messages,
  busy,
  showSuggestions,
  className,
  focused = false,
  onSend,
  onSuggestion,
  onStreamComplete,
  onCafeSelect
}: Props) => {
  const { userId } = useAuth()
  const [draft, setDraft] = useState("")
  const [speechError, setSpeechError] = useState<string | null>(null)
  const [listening, setListening] = useState(false)
  const [now, setNow] = useState(() => new Date())
  const scrollerRef = useRef<HTMLDivElement>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)

  useEffect(() => {
    const el = scrollerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(new Date())
    }, 30000)
    return () => window.clearInterval(timer)
  }, [])

  const dayTimeLabel = new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit"
  }).format(now)

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

  const handleSpeechClick = () => {
    if (busy) return

    const existing = recognitionRef.current
    if (existing && listening) {
      existing.stop()
      return
    }

    const SpeechRecognition =
      window.SpeechRecognition ?? window.webkitSpeechRecognition

    if (!SpeechRecognition) {
      setSpeechError("Speech input is not supported in this browser.")
      return
    }

    const recognition = new SpeechRecognition()
    recognitionRef.current = recognition
    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = "en-US"

    recognition.onstart = () => {
      setListening(true)
      setSpeechError(null)
    }

    recognition.onend = () => {
      setListening(false)
      recognitionRef.current = null
    }

    recognition.onerror = (event) => {
      setListening(false)
      recognitionRef.current = null
      setSpeechError(
        event.error === "not-allowed"
          ? "Microphone access was blocked."
          : "Speech input stopped. Try again."
      )
    }

    recognition.onresult = (event) => {
      let interimTranscript = ""
      let finalTranscript = ""

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        const transcript = result[0].transcript
        if (result.isFinal) {
          finalTranscript += transcript
        } else {
          interimTranscript += transcript
        }
      }

      const nextDraft = (finalTranscript || interimTranscript).trim()
      if (nextDraft) {
        setDraft(nextDraft)
      }

      const final = finalTranscript.trim()
      if (final) {
        setDraft("")
        recognition.stop()
        onSend(final)
      }
    }

    recognition.start()
  }

  return (
    <section
      aria-label="Conversation"
      className={cn(
        "grain relative flex h-full min-h-0 flex-col bg-bone transition-[border-radius,box-shadow,border-color,transform] duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)]",
        focused
          ? "overflow-hidden border border-terracotta/25 shadow-[0_32px_100px_-56px_rgba(14,42,61,0.65)]"
          : "border-r border-ink/10",
        className
      )}
    >
      <Header dayTimeLabel={dayTimeLabel} signedIn={Boolean(userId)} />

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
                "group cursor-pointer rounded-full border border-terracotta/40 bg-bone-soft px-3.5 py-2 text-[12.5px] leading-tight text-ink",
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
        className="relative z-[2] border-t border-ink/10 bg-bone px-7 py-4 sm:px-10"
      >
        <div className="flex items-center gap-3">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={busy}
            placeholder={
              listening
                ? "listening…"
                : busy
                  ? "checking shadows…"
                  : "Tell me where & when, and whether you want sun or shade"
            }
            aria-label="Message"
            className={cn(
              "min-h-[44px] max-h-32 flex-1 resize-none bg-transparent py-2.5 text-[15px] leading-5 text-ink outline-none placeholder:text-ink/35",
              "disabled:opacity-60"
            )}
          />
          <button
            type="button"
            disabled={busy}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            aria-pressed={listening}
            onClick={handleSpeechClick}
            className={cn(
              "grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-full border text-ink transition-all",
              listening
                ? "border-terracotta bg-terracotta text-bone shadow-[0_0_0_6px_rgba(199,107,69,0.12)]"
                : "border-ink/35 hover:border-terracotta hover:text-terracotta",
              "disabled:cursor-not-allowed disabled:border-ink/20 disabled:text-ink/25"
            )}
          >
            <MicIcon active={listening} />
          </button>
          <button
            type="submit"
            disabled={!draft.trim() || busy}
            aria-label="Send message"
            className={cn(
              "inline-flex h-10 shrink-0 cursor-pointer items-center justify-center rounded-full border border-ink px-5 text-[12.5px] font-medium uppercase tracking-[0.16em] text-ink",
              "transition-all hover:bg-ink hover:text-bone",
              "disabled:cursor-not-allowed disabled:border-ink/30 disabled:text-ink/30 disabled:hover:bg-transparent"
            )}
          >
            ask
          </button>
        </div>
        {speechError && (
          <p className="mt-2 text-[11px] leading-snug text-terracotta-deep">
            {speechError}
          </p>
        )}
      </form>
    </section>
  )
}

const Header = ({
  dayTimeLabel,
  signedIn
}: {
  dayTimeLabel: string
  signedIn: boolean
}) => (
  <header className="relative z-[2] flex items-start justify-between gap-4 px-7 pb-3 pt-7 sm:px-10">
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.32em] text-terracotta-deep">
        Split · {dayTimeLabel}
      </p>
      <h1 className="font-display text-[34px] leading-[1.05] tracking-tight text-ink">
        Follow the Shade
      </h1>
    </div>
    <div className="flex shrink-0 items-center gap-3 pt-1">
      <Link
        href={signedIn ? "/settings" : "/sign-in"}
        className="rounded-full border border-ink/25 px-3 py-1.5 text-[10.5px] font-medium uppercase tracking-[0.12em] text-ink/72 transition-colors hover:border-ink/40 hover:text-ink"
      >
        {signedIn ? "Preferences" : "Sign up"}
      </Link>
    </div>
  </header>
)

const MicIcon = ({ active }: { active: boolean }) => (
  <svg
    viewBox="0 0 24 24"
    className="h-4.5 w-4.5"
    fill="none"
    aria-hidden="true"
  >
    <path
      d="M12 14.25a3.25 3.25 0 0 0 3.25-3.25V6.75a3.25 3.25 0 0 0-6.5 0V11A3.25 3.25 0 0 0 12 14.25Z"
      stroke="currentColor"
      strokeWidth="1.7"
    />
    <path
      d="M18 10.75a6 6 0 0 1-12 0M12 16.75v3M9 19.75h6"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
    />
    {active && (
      <circle cx="18.5" cy="5.5" r="2" fill="currentColor" />
    )}
  </svg>
)

export default ChatPanel
