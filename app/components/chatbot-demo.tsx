"use client";

import { FormEvent, useMemo, useState } from "react";
import type { ChatResponse, MapPayload } from "@/lib/follow-the-shade/types";
import { answerFromMapPayload } from "@/lib/map-payload-adapter";

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
};

type FlexibleChatResponse = ChatResponse & {
  response?: unknown;
  message?: unknown;
  text?: unknown;
  detail?: unknown;
  error?: unknown;
};

const initialMessages: ChatMessage[] = [
  {
    role: "assistant",
    content:
      "Tell me where and when you want to sit outside in Split, and I will check the terrace sun or shade.",
  },
];

const starterPrompts = [
  "Find me a shady restaurant outside near Riva today from 3 to 5pm.",
  "I want sun around Bacvice tomorrow morning.",
  "A shaded bar near Marmontova this Saturday afternoon.",
];

export function ChatbotDemo() {
  const [threadId] = useState(() => createThreadId());
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState(starterPrompts[0]);
  const [isLoading, setIsLoading] = useState(false);
  const [payload, setPayload] = useState<MapPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage(nextMessage = input) {
    const trimmed = nextMessage.trim();
    if (!trimmed || isLoading) {
      return;
    }

    setError(null);
    setIsLoading(true);
    setInput("");
    setMessages((current) => [...current, { role: "user", content: trimmed }]);

    try {
      const response = await fetch("/chat/final_answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          thread_id: threadId,
          include_audio: false,
        }),
      });

      if (!response.ok) {
        throw new Error(`Chat request failed with ${response.status}`);
      }

      const data = (await response.json()) as FlexibleChatResponse;
      const assistantText = assistantTextFromResponse(data);
      setPayload(data.map_payload ?? null);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: assistantText },
      ]);
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "The chat request failed.";
      setError(message);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "I could not reach the chat endpoint. Check the dev server and backend env settings.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage();
  }

  return (
    <div className="grid min-h-[calc(100vh-112px)] gap-4 lg:grid-cols-[minmax(340px,430px)_1fr]">
      <section className="flex min-h-[560px] flex-col border border-stone-200 bg-white">
        <div className="border-b border-stone-200 px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-teal-700">
            Follow the Shade
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-stone-950">
            Split terrace chat
          </h1>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={
                message.role === "user"
                  ? "ml-auto max-w-[88%] bg-teal-700 px-4 py-3 text-sm leading-6 text-white"
                  : "mr-auto max-w-[92%] border border-stone-200 bg-stone-50 px-4 py-3 text-sm leading-6 text-stone-800"
              }
            >
              {message.content}
            </div>
          ))}
          {isLoading ? (
            <div className="mr-auto border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-600">
              Checking Split terrace samples...
            </div>
          ) : null}
        </div>

        <div className="border-t border-stone-200 px-5 py-4">
          <div className="mb-3 flex flex-wrap gap-2">
            {starterPrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => void sendMessage(prompt)}
                className="border border-stone-300 bg-white px-3 py-2 text-left text-xs font-medium text-stone-700 transition hover:border-teal-700 hover:text-teal-800"
              >
                {prompt}
              </button>
            ))}
          </div>

          <form onSubmit={onSubmit} className="flex gap-2">
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              className="min-w-0 flex-1 border border-stone-300 px-3 py-3 text-sm text-stone-950 outline-none transition placeholder:text-stone-400 focus:border-teal-700"
              placeholder="Ask for a shady restaurant, bar, or cafe near Riva"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="w-20 bg-stone-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-stone-400"
            >
              Send
            </button>
          </form>
          {error ? <p className="mt-2 text-xs text-red-700">{error}</p> : null}
        </div>
      </section>

      <MapPayloadPreview payload={payload} />
    </div>
  );
}

function assistantTextFromResponse(data: FlexibleChatResponse) {
  const explicitText = firstNonEmptyString(
    data.answer,
    data.response,
    data.message,
    data.text,
    data.detail,
    data.error,
  );
  if (explicitText) {
    return explicitText;
  }
  if (data.map_payload) {
    return answerFromMapPayload(data.map_payload);
  }
  return "I checked that request for Split.";
}

function firstNonEmptyString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value !== "string") {
      continue;
    }
    const trimmed = value.trim();
    if (trimmed) {
      return trimmed;
    }
  }
  return null;
}

function MapPayloadPreview({ payload }: { payload: MapPayload | null }) {
  const bounds = useMemo(() => {
    if (!payload) {
      return null;
    }
    return {
      center: payload.map.center,
      results: payload.results,
    };
  }, [payload]);

  return (
    <section className="grid min-h-[560px] gap-4 lg:grid-rows-[minmax(280px,1fr)_auto]">
      <div className="relative overflow-hidden border border-stone-200 bg-[#dce9e4]">
        <div className="absolute inset-x-0 top-0 h-24 bg-[#91c5c0]" />
        <div className="absolute bottom-0 left-0 right-0 top-20 bg-[#f4efe3]" />
        <div className="absolute left-[8%] top-[28%] h-[52%] w-[78%] rotate-[-8deg] border-y-8 border-[#d2b26f]" />
        <div className="absolute left-[44%] top-[12%] h-[72%] w-7 rotate-[17deg] bg-[#b85c3d]" />
        <div className="absolute bottom-4 left-5 border border-black/10 bg-white/90 px-3 py-2 text-xs font-medium text-stone-700">
          {payload ? payload.request.location_label : "Split map payload"}
        </div>

        {bounds?.results.map((result, index) => (
          <div
            key={result.id}
            className="absolute grid h-8 w-8 place-items-center border-2 border-white bg-teal-700 text-xs font-bold text-white shadow-sm"
            style={markerPosition(result.terrace_point, bounds.center)}
            title={result.name}
          >
            {index + 1}
          </div>
        ))}
      </div>

      <div className="border border-stone-200 bg-white">
        <div className="border-b border-stone-200 px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#b85c3d]">
            map_payload
          </p>
          <h2 className="mt-1 text-xl font-semibold text-stone-950">
            {payload?.analysis_id ?? "Waiting for a query"}
          </h2>
        </div>

        {payload ? (
          <div className="divide-y divide-stone-200">
            {payload.results.map((result, index) => (
              <article
                key={result.id}
                className="grid gap-3 px-5 py-4 md:grid-cols-[1fr_220px]"
              >
                <div>
                  <div className="flex items-center gap-3">
                    <span className="grid h-7 w-7 place-items-center bg-teal-700 text-xs font-bold text-white">
                      {index + 1}
                    </span>
                    <div>
                      <h3 className="font-semibold text-stone-950">
                        {result.name}
                      </h3>
                      <p className="text-xs text-stone-500">{result.address}</p>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-stone-700">
                    {result.exposure.summary}
                  </p>
                </div>
                <div>
                  <div className="flex gap-1">
                    {result.exposure.samples.map((sample) => (
                      <div
                        key={sample.time}
                        className={
                          sample.state === "sun"
                            ? "h-8 flex-1 bg-[#d9a441]"
                            : "h-8 flex-1 bg-[#2f7d74]"
                        }
                        title={`${sample.time}: ${sample.state}`}
                      />
                    ))}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-stone-500">
                    <span>{result.exposure.label.replace("_", " ")}</span>
                    <span>
                      {Math.round(result.exposure.match_score * 100)}%
                    </span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="px-5 py-8 text-sm leading-6 text-stone-600">
            Results will appear here from the typed map payload, not from parsed
            assistant text.
          </div>
        )}
      </div>
    </section>
  );
}

function markerPosition(
  point: { lat: number; lng: number },
  center: { lat: number; lng: number },
) {
  const x = clamp(50 + (point.lng - center.lng) * 5200, 8, 88);
  const y = clamp(50 - (point.lat - center.lat) * 7200, 10, 84);
  return {
    left: `${x}%`,
    top: `${y}%`,
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function createThreadId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `thread_${Date.now()}`;
}
