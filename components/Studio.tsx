"use client";

import Image from "next/image";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Cafe, IntentRequest } from "@/lib/types";
import { suggestions, type SuggestionId } from "@/lib/intent";
import { greet } from "@/lib/conversation";
import { createThreadId, sendFinalAnswer } from "@/lib/backend";
import type { ChatAudio } from "@/lib/follow-the-shade/types";
import {
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

type QueryOptions = {
  fromVoiceInput?: boolean;
};

type AudioContextWindow = Window & {
  webkitAudioContext?: typeof AudioContext;
};

type SonioxConnectionConfig = {
  api_key: string;
};

type SonioxTtsConfig = {
  model?: string;
  language?: string;
  voice?: string;
  audio_format?: string;
  sample_rate?: number;
};

type SonioxTtsTemporaryKeyResponse = {
  api_key: string;
  tts?: SonioxTtsConfig;
};

type SonioxChunk = Uint8Array | ArrayBuffer | ArrayBufferView;

type SonioxTtsStream = AsyncIterable<SonioxChunk> & {
  sendText: (text: string, options?: { end?: boolean }) => void;
  close?: () => void;
  cancel?: () => void;
  return?: () => void;
};

type SonioxTtsClient = {
  realtime: {
    tts: (config: {
      model: string;
      language: string;
      voice: string;
      audio_format: string;
      sample_rate: number;
    }) => Promise<SonioxTtsStream>;
  };
};

type SonioxSdkModule = {
  SonioxClient: new (options: {
    config: () => Promise<SonioxConnectionConfig>;
  }) => SonioxTtsClient;
};

const SONIOX_SDK_URL = "https://esm.sh/@soniox/client";

const base64ToArrayBuffer = (data: string): ArrayBuffer => {
  const binary = window.atob(data);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return bytes.buffer;
};

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
  const voiceAudioContextRef = useRef<AudioContext | null>(null);
  const activeVoiceNodeRef = useRef<AudioBufferSourceNode | null>(null);
  const activeVoiceElementRef = useRef<HTMLAudioElement | null>(null);
  const activeVoiceNodesRef = useRef<AudioBufferSourceNode[]>([]);
  const sonioxTtsClientRef = useRef<SonioxTtsClient | null>(null);
  const activeVoiceStreamRef = useRef<SonioxTtsStream | null>(null);
  const pendingSonioxTtsConnectionConfigRef =
    useRef<SonioxConnectionConfig | null>(null);
  const nextVoicePlaybackTimeRef = useRef(0);
  const pcmCarryByteRef = useRef<number | null>(null);

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

  useEffect(() => {
    return () => {
      activeVoiceStreamRef.current?.close?.();
      activeVoiceStreamRef.current?.cancel?.();
      activeVoiceStreamRef.current = null;
      activeVoiceNodesRef.current.forEach((source) => {
        try {
          source.stop();
        } catch {}
      });
      activeVoiceNodesRef.current = [];
      activeVoiceNodeRef.current = null;
      activeVoiceElementRef.current?.pause();
      activeVoiceElementRef.current = null;
      const context = voiceAudioContextRef.current;
      voiceAudioContextRef.current = null;
      if (context && context.state !== "closed") {
        void context.close();
      }
    };
  }, []);

  const pushMessage = useCallback((m: ChatMessageData) => {
    setMessages((prev) => [...prev, m]);
  }, []);

  const stopVoicePlayback = useCallback(() => {
    activeVoiceStreamRef.current?.close?.();
    activeVoiceStreamRef.current?.cancel?.();
    activeVoiceStreamRef.current = null;

    if (activeVoiceNodeRef.current) {
      try {
        activeVoiceNodeRef.current.stop();
      } catch {}
    }
    activeVoiceNodeRef.current = null;

    activeVoiceNodesRef.current.forEach((source) => {
      try {
        source.stop();
      } catch {}
    });
    activeVoiceNodesRef.current = [];

    nextVoicePlaybackTimeRef.current = voiceAudioContextRef.current
      ? voiceAudioContextRef.current.currentTime
      : 0;
    pcmCarryByteRef.current = null;

    activeVoiceElementRef.current?.pause();
    activeVoiceElementRef.current = null;
  }, []);

  const primeVoicePlayback = useCallback(async () => {
    if (typeof window === "undefined") {
      return;
    }

    const AudioContextClass =
      window.AudioContext ?? (window as AudioContextWindow).webkitAudioContext;
    if (!AudioContextClass) {
      return;
    }

    const context = voiceAudioContextRef.current ?? new AudioContextClass();
    voiceAudioContextRef.current = context;

    if (context.state === "suspended") {
      try {
        await context.resume();
      } catch {
        return;
      }
    }
  }, []);

  const playVoiceReply = useCallback(
    async (audio: ChatAudio | null) => {
      if (!audio?.data) {
        return;
      }

      stopVoicePlayback();

      const context = voiceAudioContextRef.current;
      if (context) {
        try {
          if (context.state === "suspended") {
            await context.resume();
          }

          const buffer = await context.decodeAudioData(
            base64ToArrayBuffer(audio.data).slice(0),
          );
          const source = context.createBufferSource();
          source.buffer = buffer;
          source.connect(context.destination);
          source.onended = () => {
            if (activeVoiceNodeRef.current === source) {
              activeVoiceNodeRef.current = null;
            }
          };
          activeVoiceNodeRef.current = source;
          source.start(0);
          return;
        } catch {
          activeVoiceNodeRef.current = null;
        }
      }

      const playback = new Audio(
        `data:${audio.mime_type};base64,${audio.data}`,
      );
      activeVoiceElementRef.current = playback;
      playback.onended = () => {
        if (activeVoiceElementRef.current === playback) {
          activeVoiceElementRef.current = null;
        }
      };
      await playback.play().catch(() => undefined);
    },
    [stopVoicePlayback],
  );

  const loadSonioxSdk = useCallback(async (): Promise<SonioxSdkModule> => {
    const dynamicImport = new Function("url", "return import(url)") as (
      url: string,
    ) => Promise<unknown>;
    const sdk = await dynamicImport(SONIOX_SDK_URL);
    return sdk as SonioxSdkModule;
  }, []);

  const fetchSonioxTtsConnectionConfig = useCallback(
    async (
      language: string | null | undefined,
    ): Promise<{
      connection: SonioxConnectionConfig;
      tts: SonioxTtsConfig;
    }> => {
      const response = await fetch("/chat/speech/tts-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_reference_id: threadId,
          language: language ?? null,
        }),
      });

      let data: Partial<SonioxTtsTemporaryKeyResponse> & { detail?: string } =
        {};
      try {
        data =
          (await response.json()) as Partial<SonioxTtsTemporaryKeyResponse> & {
            detail?: string;
          };
      } catch {
        data = {};
      }

      if (!response.ok || !data.api_key) {
        throw new Error(data.detail || "Soniox TTS is not available.");
      }

      return {
        connection: { api_key: data.api_key },
        tts: data.tts ?? {},
      };
    },
    [threadId],
  );

  const getSonioxTtsClient = useCallback(async (): Promise<SonioxTtsClient> => {
    if (sonioxTtsClientRef.current) {
      return sonioxTtsClientRef.current;
    }

    const sdk = await loadSonioxSdk();
    const client = new sdk.SonioxClient({
      config: async () => {
        if (pendingSonioxTtsConnectionConfigRef.current) {
          const config = pendingSonioxTtsConnectionConfigRef.current;
          pendingSonioxTtsConnectionConfigRef.current = null;
          return config;
        }

        const result = await fetchSonioxTtsConnectionConfig(null);
        return result.connection;
      },
    });

    sonioxTtsClientRef.current = client;
    return client;
  }, [fetchSonioxTtsConnectionConfig, loadSonioxSdk]);

  const getSpeakableText = useCallback((text: string): string => {
    return String(text || "")
      .replace(/\[[^\]]+\]\([^)]+\)/g, "")
      .replace(/\s*\[\d+\]/g, "")
      .replace(/[*_`#>]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }, []);

  const toUint8Array = useCallback((chunk: SonioxChunk): Uint8Array => {
    if (chunk instanceof Uint8Array) {
      return chunk;
    }
    if (chunk instanceof ArrayBuffer) {
      return new Uint8Array(chunk);
    }
    return new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength);
  }, []);

  const enqueuePcm16Chunk = useCallback(
    (chunk: SonioxChunk, sampleRate: number) => {
      const context = voiceAudioContextRef.current;
      if (!context) {
        return;
      }

      let bytes = toUint8Array(chunk);
      if (bytes.length === 0) {
        return;
      }

      if (pcmCarryByteRef.current !== null) {
        const combined = new Uint8Array(bytes.length + 1);
        combined[0] = pcmCarryByteRef.current;
        combined.set(bytes, 1);
        bytes = combined;
        pcmCarryByteRef.current = null;
      }

      if (bytes.length % 2 === 1) {
        pcmCarryByteRef.current = bytes[bytes.length - 1] ?? null;
        bytes = bytes.slice(0, -1);
      }

      const sampleCount = bytes.length / 2;
      if (sampleCount === 0) {
        return;
      }

      const dataView = new DataView(
        bytes.buffer,
        bytes.byteOffset,
        bytes.byteLength,
      );
      const audioBuffer = context.createBuffer(1, sampleCount, sampleRate);
      const channel = audioBuffer.getChannelData(0);

      for (let index = 0; index < sampleCount; index += 1) {
        channel[index] = dataView.getInt16(index * 2, true) / 32768;
      }

      const source = context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(context.destination);
      source.onended = () => {
        activeVoiceNodesRef.current = activeVoiceNodesRef.current.filter(
          (item) => item !== source,
        );
        if (activeVoiceNodeRef.current === source) {
          activeVoiceNodeRef.current = null;
        }
      };

      const startAt = Math.max(
        context.currentTime + 0.04,
        nextVoicePlaybackTimeRef.current,
      );
      source.start(startAt);
      nextVoicePlaybackTimeRef.current = startAt + audioBuffer.duration;
      activeVoiceNodeRef.current = source;
      activeVoiceNodesRef.current.push(source);
    },
    [toUint8Array],
  );

  const streamVoiceReply = useCallback(
    async (
      answer: string,
      language: string | null | undefined,
      fallbackAudio: ChatAudio | null = null,
    ) => {
      const text = getSpeakableText(answer);
      if (!text) {
        return;
      }

      let stream: SonioxTtsStream | null = null;

      try {
        stopVoicePlayback();
        await primeVoicePlayback();

        const ttsKey = await fetchSonioxTtsConnectionConfig(language);
        pendingSonioxTtsConnectionConfigRef.current = ttsKey.connection;
        const client = await getSonioxTtsClient();
        const ttsConfig = ttsKey.tts;
        const sampleRate = Number(ttsConfig.sample_rate) || 24000;

        stream = await client.realtime.tts({
          model: ttsConfig.model || "tts-rt-v1",
          language: ttsConfig.language || language || "en",
          voice: ttsConfig.voice || "Grace",
          audio_format: ttsConfig.audio_format || "pcm_s16le",
          sample_rate: sampleRate,
        });

        activeVoiceStreamRef.current = stream;
        stream.sendText(text, { end: true });

        let receivedChunk = false;
        for await (const chunk of stream) {
          if (activeVoiceStreamRef.current !== stream) {
            break;
          }
          receivedChunk = true;
          enqueuePcm16Chunk(chunk, sampleRate);
        }

        if (!receivedChunk && fallbackAudio) {
          await playVoiceReply(fallbackAudio);
        }
      } catch {
        if (fallbackAudio) {
          await playVoiceReply(fallbackAudio);
        }
      } finally {
        if (activeVoiceStreamRef.current === stream) {
          activeVoiceStreamRef.current = null;
        }
      }
    },
    [
      enqueuePcm16Chunk,
      fetchSonioxTtsConnectionConfig,
      getSonioxTtsClient,
      getSpeakableText,
      playVoiceReply,
      primeVoicePlayback,
      stopVoicePlayback,
    ],
  );

  const handleStreamComplete = useCallback((messageId: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, streaming: false } : m)),
    );
  }, []);

  const beginQuery = useCallback(
    async (userUtterance: string, options: QueryOptions = {}) => {
      const fromVoiceInput = options.fromVoiceInput ?? false;

      setHasStarted(true);
      requestAnimationFrame(() => mapRef.current?.resize());
      window.setTimeout(() => mapRef.current?.resize(), 720);
      pushMessage({ id: newId(), role: "user", text: userUtterance });
      setPhase({ kind: "checking" });
      stopVoicePlayback();
      mapRef.current?.clearResults();
      mapRef.current?.setShadeOpacity(0);

      try {
        const response = await sendFinalAnswer({
          message: userUtterance,
          thread_id: threadId,
          include_audio: false,
        });

        const responseText = response.answer;

        if (!response.map_payload) {
          pushMessage({
            id: newId(),
            role: "bot",
            text: responseText,
            streaming: true,
          });

          if (fromVoiceInput) {
            void streamVoiceReply(
              responseText,
              response.detected_language,
              response.audio,
            );
          }

          setPhase({ kind: "idle" });
          return;
        }

        const intent = intentFromMapPayload(response.map_payload);
        const results = resultsFromMapPayload(response.map_payload);

        pushMessage({
          id: newId(),
          role: "bot",
          text: responseText,
          streaming: true,
          intent,
          results: { items: results, intent },
        });

        void mapRef.current?.flyTo(intent.area);
        mapRef.current?.setResults(
          results,
          response.map_payload.request.preference,
        );

        if (fromVoiceInput) {
          void streamVoiceReply(
            responseText,
            response.detected_language,
            response.audio,
          );
        }

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
    [pushMessage, stopVoicePlayback, streamVoiceReply, threadId],
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
    (text: string, options?: QueryOptions) => {
      if (phase.kind !== "idle" && phase.kind !== "done") return;
      beginQuery(text, options);
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
            onPrimeVoicePlayback={primeVoicePlayback}
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
