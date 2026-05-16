"use client";

import { useEffect, useRef, useState } from "react";
import type { Cafe, CafeResult, IntentRequest } from "@/lib/types";
import { cn } from "@/lib/cn";
import IntentCard from "./IntentCard";
import CafeResultCard from "./CafeResultCard";

export type MessageRole = "user" | "bot" | "system";

export type ChatMessageData = {
  id: string;
  role: MessageRole;
  text: string;
  streaming?: boolean;
  intent?: IntentRequest;
  results?: { items: CafeResult[]; intent: IntentRequest };
  outro?: string;
};

type Props = {
  message: ChatMessageData;
  onStreamComplete?: () => void;
  onCafeSelect?: (cafe: Cafe) => void;
  onShadeSampleTime?: (time: Date) => void;
};

const STREAM_MS_PER_CHAR = 12;

const ChatMessage = ({
  message,
  onStreamComplete,
  onCafeSelect,
  onShadeSampleTime,
}: Props) => {
  const { role, text, streaming } = message;
  const isUser = role === "user";
  const isSystem = role === "system";
  const isBot = role === "bot";

  const [visibleLen, setVisibleLen] = useState(() =>
    streaming ? 0 : text.length,
  );
  const [done, setDone] = useState(() => !streaming);
  const progressRef = useRef(visibleLen);
  const onStreamCompleteRef = useRef(onStreamComplete);

  useEffect(() => {
    onStreamCompleteRef.current = onStreamComplete;
  }, [onStreamComplete]);

  useEffect(() => {
    if (!streaming) return;
    if (progressRef.current >= text.length) return;
    const id = window.setInterval(() => {
      const next = Math.min(progressRef.current + 1, text.length);
      progressRef.current = next;
      setVisibleLen(next);
      if (next >= text.length) {
        window.clearInterval(id);
        setDone(true);
        onStreamCompleteRef.current?.();
      }
    }, STREAM_MS_PER_CHAR);
    return () => window.clearInterval(id);
  }, [streaming, text.length]);

  if (isSystem) {
    return (
      <div className="fts-fade-up py-2 text-center text-[11px] font-medium uppercase tracking-[0.22em] text-ink/40">
        {text}
      </div>
    );
  }

  if (isUser) {
    return (
      <div className="fts-fade-up flex justify-end">
        <div className="max-w-[88%] rounded-md border border-ink/15 bg-ink px-4 py-2.5 text-[14.5px] leading-snug text-bone">
          {text}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex w-full justify-start", isBot && "fts-fade-up")}>
      <div className="flex max-w-[92%] gap-3">
        <div className="shrink-0 pt-1">
          <BotAvatar />
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <p
            className={cn(
              "whitespace-pre-wrap text-[15px] leading-relaxed text-ink",
              !done && "fts-caret",
            )}
          >
            {text}
          </p>

          {done && message.intent && <IntentCard intent={message.intent} />}

          {done && message.results && (
            <div className="space-y-2.5 pt-1">
              {message.results.items.map((r) => (
                <CafeResultCard
                  key={r.cafe.id}
                  result={r}
                  intent={message.results!.intent}
                  onSelect={() => onCafeSelect?.(r.cafe)}
                  onShadeSampleTime={onShadeSampleTime}
                />
              ))}
            </div>
          )}

          {done && message.outro && (
            <p className="fts-fade-up pt-1 text-[13.5px] italic leading-relaxed text-ink/65">
              {message.outro}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

const BotAvatar = () => (
  <span
    aria-hidden="true"
    className="relative flex h-7 w-7 items-center justify-center rounded-full border border-terracotta/40 bg-bone-soft"
  >
    <span className="block h-3 w-3 rounded-full bg-gold-sun shadow-[0_0_10px_2px_rgba(232,181,71,0.55)]" />
  </span>
);

export default ChatMessage;
