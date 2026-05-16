"use client";

import { UserButton } from "@clerk/nextjs";
import { FormEvent, useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/cn";

type Preferences = {
  exposure_preference: "sun" | "shade" | "either";
  favorite_areas: string[];
  default_time_preset: "morning" | "lunch" | "afternoon";
  digest_enabled: boolean;
  avoid_busy: boolean;
};

const defaultPrefs: Preferences = {
  exposure_preference: "shade",
  favorite_areas: ["Riva"],
  default_time_preset: "afternoon",
  digest_enabled: false,
  avoid_busy: false,
};

const fieldClass =
  "w-full rounded-lg border border-ink/14 bg-bone/90 px-3 py-2 text-[13px] leading-snug text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.35)] outline-none transition-[border-color,box-shadow] duration-200 focus:border-terracotta/45 focus:ring-2 focus:ring-terracotta/18";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export default function PreferencesModal({ open, onOpenChange }: Props) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [prefs, setPrefs] = useState<Preferences>(defaultPrefs);
  const [status, setStatus] = useState<string | null>(null);
  const [statusOk, setStatusOk] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  const requestClose = useCallback(() => {
    setStatus(null);
    setStatusOk(null);
    onOpenChange(false);
  }, [onOpenChange]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const response = await fetch("/api/me/preferences");
        if (response.ok && !cancelled) {
          setPrefs((await response.json()) as Preferences);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") requestClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, requestClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => dialogRef.current?.focus(), 50);
    return () => window.clearTimeout(t);
  }, [open]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus(null);
    setStatusOk(null);
    const response = await fetch("/api/me/preferences", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    });
    const ok = response.ok;
    setStatus(ok ? "Saved." : "Could not save preferences.");
    setStatusOk(ok);
  }

  if (typeof document === "undefined" || !open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6"
      role="presentation"
    >
      <button
        type="button"
        aria-label="Close preferences"
        className="absolute inset-0 bg-charcoal/40 backdrop-blur-md transition-opacity"
        onClick={requestClose}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          "grain relative z-[1] max-h-[min(720px,calc(100dvh-48px))] w-full max-w-xl overflow-hidden rounded-[2rem] border border-terracotta/25 bg-bone outline-none focus:outline-none",
          "shadow-[0_32px_100px_-56px_rgba(14,42,61,0.65)]",
          "animate-[fts-chat-enter_720ms_cubic-bezier(0.2,0.8,0.2,1)_both]",
        )}
      >
        <div className="relative z-[2] max-h-[inherit] overflow-y-auto overscroll-contain px-7 pb-6 pt-7 sm:px-10">
          <header className="mb-4 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h1
                id={titleId}
                className="font-display -translate-x-[2px] text-[1.65rem] leading-[1.06] tracking-tight text-ink sm:text-[1.75rem]"
              >
                Your preferences
              </h1>
            </div>
            <div className="flex shrink-0 items-center gap-2.5 pt-1">
              <div className="shrink-0 transition-transform duration-300 hover:scale-[1.03]">
                <UserButton />
              </div>
            </div>
          </header>

          {loading ? (
            <div className="space-y-2 py-0.5">
              <div className="h-9 animate-pulse rounded-lg bg-ink/8" />
              <div className="h-9 animate-pulse rounded-lg bg-ink/8" />
              <div className="h-9 animate-pulse rounded-lg bg-ink/8" />
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <section className="space-y-2.5">
                <h2 className="font-mono text-[9px] uppercase tracking-[0.18em] text-terracotta-deep">
                  Where & how you sit
                </h2>
                <label className="block">
                  <span className="mb-1 block text-[12.5px] font-medium text-ink">
                    Sun or shade
                  </span>
                  <select
                    className={fieldClass}
                    value={prefs.exposure_preference}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        exposure_preference: e.target
                          .value as Preferences["exposure_preference"],
                      })
                    }
                  >
                    <option value="shade">Shade</option>
                    <option value="sun">Sun</option>
                    <option value="either">Either</option>
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1 block text-[12.5px] font-medium text-ink">
                    Favorite area
                  </span>
                  <input
                    className={fieldClass}
                    value={prefs.favorite_areas[0] ?? ""}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        favorite_areas: [e.target.value.trim() || "Riva"],
                      })
                    }
                  />
                </label>
              </section>

              <section className="space-y-2.5 border-t border-ink/10 pt-4">
                <h2 className="font-mono text-[9px] uppercase tracking-[0.18em] text-terracotta-deep">
                  Default time
                </h2>
                <label className="block">
                  <span className="mb-1 block text-[12.5px] font-medium text-ink">
                    When you usually ask
                  </span>
                  <select
                    className={fieldClass}
                    value={prefs.default_time_preset}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        default_time_preset: e.target
                          .value as Preferences["default_time_preset"],
                      })
                    }
                  >
                    <option value="morning">Morning</option>
                    <option value="lunch">Lunch</option>
                    <option value="afternoon">Afternoon</option>
                  </select>
                </label>
              </section>

              <section className="space-y-3 border-t border-ink/10 pt-6">
                <h2 className="font-mono text-[10px] uppercase tracking-[0.2em] text-terracotta-deep">
                  Extras
                </h2>
                <label
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-xl border border-ink/10 bg-bone/50 px-3.5 py-3 transition-colors duration-200 hover:border-terracotta/25 hover:bg-bone/80",
                  )}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4 shrink-0 rounded border-ink/30 text-terracotta focus:ring-terracotta/40"
                    checked={prefs.avoid_busy}
                    onChange={(e) =>
                      setPrefs({ ...prefs, avoid_busy: e.target.checked })
                    }
                  />
                  <span className="text-[12.5px] leading-snug text-ink">
                    Prefer less busy spots (Foursquare)
                  </span>
                </label>
                <label
                  className={cn(
                    "flex cursor-pointer items-start gap-2.5 rounded-lg border border-ink/10 bg-bone/50 px-3 py-2 transition-colors duration-200 hover:border-terracotta/25 hover:bg-bone/80",
                  )}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4 shrink-0 rounded border-ink/30 text-terracotta focus:ring-terracotta/40"
                    checked={prefs.digest_enabled}
                    onChange={(e) =>
                      setPrefs({ ...prefs, digest_enabled: e.target.checked })
                    }
                  />
                  <span className="text-[12.5px] leading-snug text-ink">
                    Daily digest (coming soon)
                  </span>
                </label>
              </section>

              <div className="flex flex-wrap items-center gap-2 border-t border-ink/10 pt-4">
                <button
                  type="submit"
                  className={cn(
                    "inline-flex h-10 shrink-0 cursor-pointer items-center justify-center rounded-full border border-ink px-5 text-[12.5px] font-medium uppercase tracking-[0.16em] text-ink",
                    "transition-all hover:bg-ink hover:text-bone",
                    "active:scale-[0.98]",
                  )}
                >
                  Save
                </button>
                {status ? (
                  <p
                    key={status}
                    className={cn(
                      "text-[12.5px] fts-settings-success",
                      statusOk === true && "font-medium text-terracotta-deep",
                      statusOk === false && "text-terracotta-deep",
                    )}
                    role="status"
                  >
                    {status}
                  </p>
                ) : null}
              </div>
            </form>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
