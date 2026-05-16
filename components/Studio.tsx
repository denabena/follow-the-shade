"use client";

import Image from "next/image";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Cafe, IntentRequest } from "@/lib/types";
import { suggestions, type SuggestionId } from "@/lib/intent";
import { greet } from "@/lib/conversation";
import { createThreadId, sendFinalAnswer } from "@/lib/backend";
import {
  answerFromMapPayload,
  intentFromMapPayload,
  resultsFromMapPayload,
} from "@/lib/map-payload-adapter";
import backgroundImage from "@/assets/background.png";
import ChatPanel from "./ChatPanel";
import PreferencesModal from "./PreferencesModal";
import MapPanel, { type MapPanelHandle } from "./MapPanel";
import type { ChatMessageData } from "./ChatMessage";

type Phase =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "done"; intent: IntentRequest };

const newId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

const StudioContent = () => {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<ChatMessageData[]>([
    { id: newId(), role: "bot", text: greet(), streaming: true },
  ]);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [hasStarted, setHasStarted] = useState(false);
  const [threadId] = useState(() => createThreadId());
  const [preferencesOpen, setPreferencesOpen] = useState(false);

  const mapRef = useRef<MapPanelHandle>(null);

  useEffect(() => {
    if (searchParams.get("prefs") !== "1") return;
    const url = new URL(window.location.href);
    url.searchParams.delete("prefs");
    const q = url.searchParams.toString();
    window.history.replaceState(
      {},
      "",
      `${url.pathname}${q ? `?${q}` : ""}${url.hash}`,
    );
    const t = window.setTimeout(() => {
      setPreferencesOpen(true);
    }, 0);
    return () => window.clearTimeout(t);
  }, [searchParams]);

  const pushMessage = useCallback((m: ChatMessageData) => {
    setMessages((prev) => [...prev, m]);
  }, []);

  const handleStreamComplete = useCallback((messageId: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, streaming: false } : m)),
    );
  }, []);

  const beginQuery = useCallback(
    async (userUtterance: string) => {
      setHasStarted(true);
      requestAnimationFrame(() => mapRef.current?.resize());
      window.setTimeout(() => mapRef.current?.resize(), 720);
      pushMessage({ id: newId(), role: "user", text: userUtterance });
      setPhase({ kind: "checking" });
      mapRef.current?.clearResults();
      mapRef.current?.setShadeOpacity(0);

      try {
        const response = await sendFinalAnswer({
          message: userUtterance,
          thread_id: threadId,
          include_audio: false,
        });

        if (!response.map_payload) {
          pushMessage({
            id: newId(),
            role: "bot",
            text: response.answer,
            streaming: true,
          });
          setPhase({ kind: "idle" });
          return;
        }

        const intent = intentFromMapPayload(response.map_payload);
        const results = resultsFromMapPayload(response.map_payload);
        await mapRef.current?.flyTo(intent.area);
        mapRef.current?.setResults(
          results,
          response.map_payload.request.preference,
        );

        pushMessage({
          id: newId(),
          role: "bot",
          text: answerFromMapPayload(response.map_payload),
          streaming: true,
          intent,
          results: { items: results, intent },
        });
        setPhase({ kind: "done", intent });
      } catch (err) {
        const detail = err instanceof Error ? err.message : "Unknown error";
        pushMessage({
          id: newId(),
          role: "bot",
          text: `I could not reach the backend chat endpoint (${detail}). Check FOLLOW_THE_SHADE_API_BASE_URL and the backend server.`,
          streaming: true,
        });
        setPhase({ kind: "idle" });
      }
    },
    [pushMessage, threadId],
  );

  const handleSuggestion = useCallback(
    (id: SuggestionId) => {
      if (phase.kind !== "idle" && phase.kind !== "done") return;
      const suggestion = suggestions.find((item) => item.id === id);
      if (!suggestion) return;
      beginQuery(suggestion.utterance);
    },
    [phase, beginQuery],
  );

  const handleSend = useCallback(
    (text: string) => {
      if (phase.kind !== "idle" && phase.kind !== "done") return;
      beginQuery(text);
    },
    [phase, beginQuery],
  );

  const handleCafeSelect = useCallback((cafe: Cafe) => {
    mapRef.current?.focusCafe(cafe);
  }, []);

  const handleMapReady = useCallback(() => undefined, []);

  const showSuggestions =
    (phase.kind === "idle" || phase.kind === "done") &&
    messages.filter((m) => m.role === "user").length === 0;

  const busy = phase.kind === "checking";
  const mapActive = hasStarted;

  return (
    <div className="relative h-screen w-full overflow-hidden bg-bone">
      <div
        aria-hidden="true"
        className={[
          "pointer-events-none absolute inset-0 z-[1] transition-opacity duration-700 ease-out",
          mapActive ? "opacity-0" : "opacity-[0.06]",
        ].join(" ")}
      >
        <Image
          src={backgroundImage}
          alt=""
          fill
          sizes="100vw"
          className="h-full w-full object-cover object-center"
        />
      </div>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div
          className={[
            "absolute left-1/2 top-1/2 h-[70vmin] w-[70vmin] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold-sun/25 blur-3xl transition-[opacity,transform] duration-1000 ease-out",
            mapActive ? "scale-125 opacity-0" : "scale-100 opacity-100",
          ].join(" ")}
        />
        <div className="absolute -right-24 bottom-0 h-[55vmin] w-[55vmin] rounded-full bg-terracotta/10 blur-3xl" />
        <div className="absolute -left-20 top-0 h-[45vmin] w-[45vmin] rounded-full bg-ink/10 blur-3xl" />
      </div>

      <div
        className={[
          "relative z-[2] h-full w-full transition-[grid-template-columns,grid-template-rows,padding,gap] duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)]",
          mapActive
            ? "grid grid-cols-1 grid-rows-[minmax(0,52%)_minmax(0,48%)] gap-0 p-0 lg:grid-cols-[minmax(420px,38%)_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)]"
            : "p-6",
        ].join(" ")}
      >
        <div
          className={[
            "min-h-0 min-w-0 overflow-hidden transition-[transform,opacity] duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)]",
            mapActive
              ? "h-full translate-y-0 opacity-100"
              : "absolute left-1/2 top-1/2 h-[min(920px,calc(100dvh-96px))] w-[min(980px,calc(100vw-48px))] -translate-x-1/2 -translate-y-1/2 rounded-[2rem] animate-[fts-chat-enter_720ms_cubic-bezier(0.2,0.8,0.2,1)_both]",
          ].join(" ")}
        >
          <ChatPanel
            messages={messages}
            busy={busy}
            showSuggestions={showSuggestions}
            focused={!mapActive}
            className={mapActive ? "" : "rounded-[2rem]"}
            onSend={handleSend}
            onSuggestion={handleSuggestion}
            onStreamComplete={handleStreamComplete}
            onCafeSelect={handleCafeSelect}
            onOpenPreferences={() => setPreferencesOpen(true)}
          />
        </div>
        <div
          className={[
            "relative min-h-0 min-w-0 overflow-hidden bg-bone-deep transition-[opacity,transform] duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)]",
            mapActive
              ? "pointer-events-auto h-full translate-y-0 opacity-100"
              : "pointer-events-none absolute inset-x-6 bottom-6 h-[38vh] translate-y-6 opacity-0 sm:inset-x-8",
          ].join(" ")}
        >
          <MapPanel
            ref={mapRef}
            onReady={handleMapReady}
            onCafeClick={handleCafeSelect}
          />
        </div>
      </div>
      <PreferencesModal
        open={preferencesOpen}
        onOpenChange={setPreferencesOpen}
      />
    </div>
  );
};

const Studio = () => (
  <Suspense fallback={null}>
    <StudioContent />
  </Suspense>
);

export default Studio;
