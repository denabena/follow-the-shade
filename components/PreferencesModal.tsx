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

type NotificationSchedule = {
  enabled: boolean;
  email?: string | null;
  days_of_week: number[];
  send_time_local: string;
  timezone: string;
  area: string;
  time_window_preset: "morning" | "lunch" | "afternoon";
  exposure_preference: "sun" | "shade" | "either";
  last_sent_at_utc?: string | null;
};

const defaultPrefs: Preferences = {
  exposure_preference: "shade",
  favorite_areas: ["Riva"],
  default_time_preset: "afternoon",
  digest_enabled: false,
  avoid_busy: false,
};

const defaultSchedule: NotificationSchedule = {
  enabled: false,
  email: null,
  days_of_week: [5],
  send_time_local: "12:00",
  timezone: "Europe/Zagreb",
  area: "Riva",
  time_window_preset: "afternoon",
  exposure_preference: "shade",
  last_sent_at_utc: null,
};

const weekdays = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
  { value: 3, label: "Thu" },
  { value: 4, label: "Fri" },
  { value: 5, label: "Sat" },
  { value: 6, label: "Sun" },
];

const splitAreas = [
  "Riva",
  "Diocletian Palace",
  "Marmontova",
  "Prokurative",
  "Matejuska",
  "Varos",
  "Bacvice",
  "Firule",
  "Znjan",
  "West Coast",
  "Sustipan",
];

const fieldClass =
  "w-full rounded-lg border border-ink/14 bg-bone/90 px-3 py-2 text-[13px] leading-snug text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.35)] outline-none transition-[border-color,box-shadow] duration-200 focus:border-terracotta/45 focus:ring-2 focus:ring-terracotta/18";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export default function PreferencesModal({ open, onOpenChange }: Props) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<"preferences" | "notifications">(
    "preferences",
  );
  const [prefs, setPrefs] = useState<Preferences>(defaultPrefs);
  const [schedule, setSchedule] =
    useState<NotificationSchedule>(defaultSchedule);
  const [status, setStatus] = useState<string | null>(null);
  const [statusOk, setStatusOk] = useState<boolean | null>(null);
  const [notificationStatus, setNotificationStatus] = useState<string | null>(
    null,
  );
  const [notificationStatusOk, setNotificationStatusOk] = useState<
    boolean | null
  >(null);
  const [loading, setLoading] = useState(true);

  const requestClose = useCallback(() => {
    setStatus(null);
    setStatusOk(null);
    setNotificationStatus(null);
    setNotificationStatusOk(null);
    onOpenChange(false);
  }, [onOpenChange]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const [preferencesResult, notificationsResult] =
          await Promise.allSettled([
            fetch("/api/me/preferences"),
            fetch("/api/me/notifications"),
          ]);

        if (
          preferencesResult.status === "fulfilled" &&
          preferencesResult.value.ok &&
          !cancelled
        ) {
          const nextPrefs =
            (await preferencesResult.value.json()) as Preferences;
          setPrefs(nextPrefs);
          setSchedule((current) => ({
            ...current,
            area: nextPrefs.favorite_areas[0] ?? current.area,
            time_window_preset: nextPrefs.default_time_preset,
            exposure_preference: nextPrefs.exposure_preference,
          }));
        }

        if (
          notificationsResult.status === "fulfilled" &&
          notificationsResult.value.ok &&
          !cancelled
        ) {
          setSchedule(
            (await notificationsResult.value.json()) as NotificationSchedule,
          );
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

  async function onNotificationSubmit(event: FormEvent) {
    event.preventDefault();
    setNotificationStatus(null);
    setNotificationStatusOk(null);
    const response = await fetch("/api/me/notifications", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(schedule),
    });
    const ok = response.ok;
    if (ok) {
      setSchedule((await response.json()) as NotificationSchedule);
    }
    setNotificationStatus(
      ok ? "Notification schedule saved." : "Could not save notification schedule.",
    );
    setNotificationStatusOk(ok);
  }

  async function sendTestEmail() {
    setNotificationStatus(null);
    setNotificationStatusOk(null);
    const response = await fetch("/api/me/notifications/test", {
      method: "POST",
    });
    if (!response.ok) {
      setNotificationStatus(
        await responseMessage(response, "Could not send test email."),
      );
      setNotificationStatusOk(false);
      return;
    }
    const result = (await response.json()) as { sent: boolean; detail?: string };
    setNotificationStatus(
      result.sent ? "Test email sent." : result.detail ?? "No email was sent.",
    );
    setNotificationStatusOk(result.sent);
  }

  async function responseMessage(response: Response, fallback: string) {
    try {
      const body = (await response.json()) as {
        detail?: string;
        message?: string;
      };
      return body.detail ?? body.message ?? fallback;
    } catch {
      return fallback;
    }
  }

  function toggleDay(day: number) {
    const selected = schedule.days_of_week.includes(day);
    const nextDays = selected
      ? schedule.days_of_week.filter((value) => value !== day)
      : [...schedule.days_of_week, day];
    setSchedule({
      ...schedule,
      days_of_week: (nextDays.length ? nextDays : [day]).sort(),
    });
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

          <div
            className="mb-5 grid grid-cols-2 rounded-full border border-ink/10 bg-bone/60 p-1 text-[11px] font-medium uppercase tracking-[0.16em]"
            role="tablist"
            aria-label="Preference sections"
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "preferences"}
              className={cn(
                "rounded-full px-3 py-2 transition-colors",
                activeTab === "preferences"
                  ? "bg-ink text-bone"
                  : "text-ink/65 hover:text-ink",
              )}
              onClick={() => setActiveTab("preferences")}
            >
              Preferences
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "notifications"}
              className={cn(
                "rounded-full px-3 py-2 transition-colors",
                activeTab === "notifications"
                  ? "bg-ink text-bone"
                  : "text-ink/65 hover:text-ink",
              )}
              onClick={() => setActiveTab("notifications")}
            >
              Notifications
            </button>
          </div>

          {loading ? (
            <div className="space-y-2 py-0.5">
              <div className="h-9 animate-pulse rounded-lg bg-ink/8" />
              <div className="h-9 animate-pulse rounded-lg bg-ink/8" />
              <div className="h-9 animate-pulse rounded-lg bg-ink/8" />
            </div>
          ) : (
            <div>
              {activeTab === "preferences" ? (
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
              ) : (
                <form onSubmit={onNotificationSubmit} className="space-y-4">
                  <section className="space-y-3">
                    <h2 className="font-mono text-[9px] uppercase tracking-[0.18em] text-terracotta-deep">
                      Email notifications
                    </h2>
                    <p className="text-[12.5px] leading-snug text-ink/65">
                      Pick the days and local time for a fresh Split cafe digest.
                    </p>
                    <label
                      className={cn(
                        "flex cursor-pointer items-start gap-3 rounded-xl border border-ink/10 bg-bone/50 px-3.5 py-3 transition-colors duration-200 hover:border-terracotta/25 hover:bg-bone/80",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5 size-4 shrink-0 rounded border-ink/30 text-terracotta focus:ring-terracotta/40"
                        checked={schedule.enabled}
                        onChange={(e) =>
                          setSchedule({
                            ...schedule,
                            enabled: e.target.checked,
                          })
                        }
                      />
                      <span className="text-[12.5px] leading-snug text-ink">
                        Send scheduled cafe picks
                      </span>
                    </label>
                  </section>

                  <section className="space-y-2.5 border-t border-ink/10 pt-4">
                    <h2 className="font-mono text-[9px] uppercase tracking-[0.18em] text-terracotta-deep">
                      Days
                    </h2>
                    <div className="flex flex-wrap gap-2">
                      {weekdays.map((day) => {
                        const selected = schedule.days_of_week.includes(
                          day.value,
                        );
                        return (
                          <button
                            key={day.value}
                            type="button"
                            className={cn(
                              "rounded-full border px-3 py-1.5 text-[11px] font-medium transition-colors",
                              selected
                                ? "border-terracotta-deep bg-terracotta-deep text-bone"
                                : "border-ink/14 bg-bone/70 text-ink hover:border-terracotta/30",
                            )}
                            onClick={() => toggleDay(day.value)}
                          >
                            {day.label}
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  <section className="grid gap-3 border-t border-ink/10 pt-4 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 block text-[12.5px] font-medium text-ink">
                        Send time
                      </span>
                      <input
                        type="time"
                        className={fieldClass}
                        value={schedule.send_time_local}
                        onChange={(e) =>
                          setSchedule({
                            ...schedule,
                            send_time_local: e.target.value,
                          })
                        }
                      />
                    </label>

                    <label className="block">
                      <span className="mb-1 block text-[12.5px] font-medium text-ink">
                        Area
                      </span>
                      <select
                        className={fieldClass}
                        value={schedule.area}
                        onChange={(e) =>
                          setSchedule({ ...schedule, area: e.target.value })
                        }
                      >
                        {splitAreas.map((area) => (
                          <option key={area} value={area}>
                            {area}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="block">
                      <span className="mb-1 block text-[12.5px] font-medium text-ink">
                        Window
                      </span>
                      <select
                        className={fieldClass}
                        value={schedule.time_window_preset}
                        onChange={(e) =>
                          setSchedule({
                            ...schedule,
                            time_window_preset: e.target
                              .value as NotificationSchedule["time_window_preset"],
                          })
                        }
                      >
                        <option value="morning">Morning</option>
                        <option value="lunch">Lunch</option>
                        <option value="afternoon">Afternoon</option>
                      </select>
                    </label>

                    <label className="block">
                      <span className="mb-1 block text-[12.5px] font-medium text-ink">
                        Preference
                      </span>
                      <select
                        className={fieldClass}
                        value={schedule.exposure_preference}
                        onChange={(e) =>
                          setSchedule({
                            ...schedule,
                            exposure_preference: e.target
                              .value as NotificationSchedule["exposure_preference"],
                          })
                        }
                      >
                        <option value="shade">Shade</option>
                        <option value="sun">Sun</option>
                        <option value="either">Either</option>
                      </select>
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
                    <button
                      type="button"
                      className={cn(
                        "inline-flex h-10 shrink-0 cursor-pointer items-center justify-center rounded-full border border-terracotta-deep px-5 text-[12.5px] font-medium uppercase tracking-[0.16em] text-terracotta-deep",
                        "transition-all hover:bg-terracotta-deep hover:text-bone",
                        "active:scale-[0.98]",
                      )}
                      onClick={sendTestEmail}
                    >
                      Test email
                    </button>
                    {notificationStatus ? (
                      <p
                        key={notificationStatus}
                        className={cn(
                          "text-[12.5px] fts-settings-success",
                          notificationStatusOk === true &&
                            "font-medium text-terracotta-deep",
                          notificationStatusOk === false &&
                            "text-terracotta-deep",
                        )}
                        role="status"
                      >
                        {notificationStatus}
                      </p>
                    ) : null}
                  </div>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
