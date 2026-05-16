"use client"

import { useAuth } from "@clerk/nextjs"
import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import type { Cafe } from "@/lib/types"
import { cn } from "@/lib/cn"
import { formatZagrebDayTimeLabel } from "@/lib/format"
import { suggestions, type SuggestionId } from "@/lib/intent"
import ChatMessage, { type ChatMessageData } from "./ChatMessage"
import { SunGlyph } from "@/components/SunGlyph"

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

type WeatherReport = {
  temperatureC: number
  feelsLikeC: number
  windKmh: number
  condition: string
}

const weatherLabelFromCode = (code: number): string => {
  if (code === 0) return "Clear sky"
  if ([1, 2].includes(code)) return "Partly cloudy"
  if (code === 3) return "Overcast"
  if ([45, 48].includes(code)) return "Foggy"
  if ([51, 53, 55, 56, 57].includes(code)) return "Drizzle"
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return "Rain"
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "Snow"
  if ([95, 96, 99].includes(code)) return "Thunderstorm"
  return "Variable conditions"
}

/** ~4 lines; grows until this, then scrolls inside the field */
const TEXTAREA_MAX_HEIGHT_PX = 128

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
  /** Updates map shadow simulator to match a timeline sample (café result cards). */
  onShadeSampleTime?: (time: Date) => void
  onOpenPreferences: () => void
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
  onCafeSelect,
  onShadeSampleTime,
  onOpenPreferences
}: Props) => {
  const { userId } = useAuth()
  const [draft, setDraft] = useState("")
  const [speechError, setSpeechError] = useState<string | null>(null)
  const [listening, setListening] = useState(false)
  const [now, setNow] = useState(() => new Date())
  const [weather, setWeather] = useState<WeatherReport | null>(null)
  const [weatherStatus, setWeatherStatus] = useState<"loading" | "ready" | "error">(
    "loading"
  )
  const scrollerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "0px"
    const contentHeight = el.scrollHeight
    if (contentHeight <= TEXTAREA_MAX_HEIGHT_PX) {
      el.style.height = `${contentHeight}px`
      el.style.overflowY = "hidden"
    } else {
      el.style.height = `${TEXTAREA_MAX_HEIGHT_PX}px`
      el.style.overflowY = "auto"
    }
  }, [draft, busy, listening])

  useEffect(() => {
    const el = scrollerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  }, [messages, busy])

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(new Date())
    }, 30000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadWeather = async () => {
      try {
        setWeatherStatus("loading")
        const res = await fetch(
          "https://api.open-meteo.com/v1/forecast?latitude=43.5081&longitude=16.4402&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=auto",
          { cache: "no-store" }
        )
        if (!res.ok) throw new Error("weather_unavailable")

        const data = (await res.json()) as {
          current?: {
            temperature_2m?: number
            apparent_temperature?: number
            weather_code?: number
            wind_speed_10m?: number
          }
        }

        const current = data.current
        if (
          !current ||
          current.temperature_2m === undefined ||
          current.apparent_temperature === undefined ||
          current.weather_code === undefined ||
          current.wind_speed_10m === undefined
        ) {
          throw new Error("weather_payload_invalid")
        }

        if (!cancelled) {
          setWeather({
            temperatureC: current.temperature_2m,
            feelsLikeC: current.apparent_temperature,
            windKmh: current.wind_speed_10m,
            condition: weatherLabelFromCode(current.weather_code)
          })
          setWeatherStatus("ready")
        }
      } catch {
        if (!cancelled) {
          setWeatherStatus("error")
        }
      }
    }

    void loadWeather()
    const refreshTimer = window.setInterval(() => {
      void loadWeather()
    }, 10 * 60 * 1000)

    return () => {
      cancelled = true
      window.clearInterval(refreshTimer)
    }
  }, [])

  const dayTimeLabel = formatZagrebDayTimeLabel(now)

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
      aria-busy={busy}
      aria-label="Conversation"
      className={cn(
        "grain relative flex h-full min-h-0 flex-col bg-bone transition-[border-radius,box-shadow,border-color,transform] duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)]",
        focused
          ? "overflow-hidden border border-terracotta/25 shadow-[0_32px_100px_-56px_rgba(14,42,61,0.65)]"
          : "border-r border-ink/10",
        className
      )}
    >
      <Header
        dayTimeLabel={dayTimeLabel}
        signedIn={Boolean(userId)}
        weather={weather}
        weatherStatus={weatherStatus}
        onOpenPreferences={onOpenPreferences}
      />

      <div
        ref={scrollerRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        className="relative z-[2] flex flex-1 flex-col overflow-y-auto px-7 pb-6 pt-2 sm:px-10"
      >
        <div className="space-y-6">
          {messages.map((m) => (
            <ChatMessage
              key={m.id}
              message={m}
              onStreamComplete={() => onStreamComplete(m.id)}
              onCafeSelect={onCafeSelect}
              onShadeSampleTime={onShadeSampleTime}
            />
          ))}
          {busy ? (
            <div
              role="status"
              aria-live="polite"
              aria-atomic="true"
              className="fts-fade-up flex items-start gap-3 rounded-xl border border-terracotta/20 bg-gradient-to-br from-bone-soft/90 to-bone/80 px-4 py-3.5 shadow-[0_8px_28px_-18px_rgba(14,42,61,0.35)]"
            >
              <div
                className="fts-sun-spin mt-0.5 h-10 w-10 shrink-0 drop-shadow-[0_2px_10px_rgba(232,181,71,0.35)]"
                aria-hidden={true}
              >
                <SunGlyph />
              </div>
              <div className="min-w-0 pt-0.5">
                <p className="font-display text-[15px] leading-snug text-ink">
                  Tracing rooftops for your window…
                </p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-terracotta-deep">
                  Checking cafes · buildings · sun path
                </p>
              </div>
            </div>
          ) : null}
        </div>
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
        className={cn(
          "relative z-[2] border-t bg-bone px-7 py-4 sm:px-10",
          focused ? "border-ink/10" : "border-ink/[0.06]",
          busy && "pt-[calc(1rem+2px)]",
        )}
      >
        {busy ? (
          <div className="fts-loading-bar-track z-[3]" aria-hidden>
            <div className="fts-loading-bar-glow" />
          </div>
        ) : null}
        <div className="flex items-end gap-3">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={busy}
            placeholder={
              listening
                ? "Listening…"
                : busy
                  ? "Checking shadows…"
                  : "Where & when - sun or shade?"
            }
            aria-label="Where and when, sun or shade"
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
  signedIn,
  weather,
  weatherStatus,
  onOpenPreferences
}: {
  dayTimeLabel: string
  signedIn: boolean
  weather: WeatherReport | null
  weatherStatus: "loading" | "ready" | "error"
  onOpenPreferences: () => void
}) => (
  <header className="relative z-[2] px-4 pb-2 pt-5 sm:px-7 sm:pb-3 sm:pt-7 lg:px-10">
    <p className="font-mono text-[9px] uppercase tracking-[0.28em] text-terracotta-deep sm:text-[10px] sm:tracking-[0.32em]">
      Split · {dayTimeLabel}
    </p>
    <div className="mt-1 flex items-center justify-between gap-3 sm:mt-1.5 sm:gap-4">
      <h1 className="font-display -translate-x-[2px] min-w-0 flex-1 text-[1.625rem] leading-[1.06] tracking-tight text-ink sm:text-[32px] sm:leading-[1.05] lg:text-[34px]">
        Follow the Shade
      </h1>
      <div className="shrink-0">
        {signedIn ? (
          <button
            type="button"
            onClick={onOpenPreferences}
            className="rounded-full border border-ink/25 px-2.5 py-2 text-[10px] font-medium uppercase tracking-[0.12em] text-ink/72 transition-colors min-[360px]:px-3 min-[360px]:py-1.5 min-[360px]:text-[10.5px] sm:hover:border-ink/40 sm:hover:text-ink"
          >
            <span className="sm:hidden">Prefs</span>
            <span className="hidden sm:inline">Preferences</span>
          </button>
        ) : (
          <Link
            href="/sign-in"
            className="rounded-full border border-ink/25 px-2.5 py-2 text-[10px] font-medium uppercase tracking-[0.12em] text-ink/72 transition-colors min-[360px]:px-3 min-[360px]:py-1.5 min-[360px]:text-[10.5px] sm:hover:border-ink/40 sm:hover:text-ink"
          >
            Sign up
          </Link>
        )}
      </div>
    </div>
    {weatherStatus === "ready" && weather ? (
      <p
        className="mt-2 flex max-w-full flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] leading-snug text-ink/62"
        aria-live="polite"
      >
        <span className="font-medium text-ink">{Math.round(weather.temperatureC)}°C</span>
        <span className="text-ink/32" aria-hidden>
          ·
        </span>
        <span>{weather.condition}</span>
        <span className="text-ink/32" aria-hidden>
          ·
        </span>
        <span>Feels {Math.round(weather.feelsLikeC)}°C</span>
        <span className="text-ink/32" aria-hidden>
          ·
        </span>
        <span>Wind {Math.round(weather.windKmh)} km/h</span>
      </p>
    ) : weatherStatus === "loading" ? (
      <p className="mt-2 text-[11px] text-ink/45">Loading weather in Split…</p>
    ) : null}
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
