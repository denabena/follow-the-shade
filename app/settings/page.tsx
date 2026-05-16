"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

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

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<Preferences>(defaultPrefs);
  const [schedule, setSchedule] =
    useState<NotificationSchedule>(defaultSchedule);
  const [status, setStatus] = useState<string | null>(null);
  const [notificationStatus, setNotificationStatus] = useState<string | null>(
    null,
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      setLoading(false);
      const [preferencesResult, notificationsResult] = await Promise.allSettled([
        fetch("/api/me/preferences"),
        fetch("/api/me/notifications"),
      ]);

      if (
        preferencesResult.status === "fulfilled" &&
        preferencesResult.value.ok
      ) {
        const nextPrefs = (await preferencesResult.value.json()) as Preferences;
        setPrefs(nextPrefs);
        setSchedule((current) => ({
          ...current,
          area: nextPrefs.favorite_areas[0] ?? current.area,
          time_window_preset: nextPrefs.default_time_preset,
          exposure_preference: nextPrefs.exposure_preference,
        }));
      } else {
        setStatus("Using default preferences. Could not load saved defaults.");
      }

      if (
        notificationsResult.status === "fulfilled" &&
        notificationsResult.value.ok
      ) {
        setSchedule(
          (await notificationsResult.value.json()) as NotificationSchedule,
        );
      } else {
        setNotificationStatus(
          "Using default notification settings. Could not load saved schedule.",
        );
      }
    })();
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus(null);
    const response = await fetch("/api/me/preferences", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    });
    setStatus(response.ok ? "Saved." : "Could not save preferences.");
  }

  async function onNotificationSubmit(event: FormEvent) {
    event.preventDefault();
    setNotificationStatus(null);
    const response = await fetch("/api/me/notifications", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(schedule),
    });
    if (response.ok) {
      setSchedule((await response.json()) as NotificationSchedule);
      setNotificationStatus("Notification schedule saved.");
      return;
    }
    setNotificationStatus("Could not save notification schedule.");
  }

  async function sendTestEmail() {
    setNotificationStatus(null);
    const response = await fetch("/api/me/notifications/test", {
      method: "POST",
    });
    if (!response.ok) {
      setNotificationStatus(await responseMessage(response, "Could not send test email."));
      return;
    }
    const result = (await response.json()) as { sent: boolean; detail?: string };
    setNotificationStatus(
      result.sent ? "Test email sent." : result.detail ?? "No email was sent.",
    );
  }

  async function responseMessage(response: Response, fallback: string) {
    try {
      const body = (await response.json()) as { detail?: string; message?: string };
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

  return (
    <main className="mx-auto max-w-2xl px-6 py-10 text-ink">
      <header className="mb-8 flex items-center justify-between">
        <SettingsTitle />
        <UserButton />
      </header>
      {loading ? (
        <p className="text-sm text-ink/60">Loading…</p>
      ) : (
        <div className="space-y-8">
          <form
            onSubmit={onSubmit}
            className="space-y-5 rounded-3xl border border-ink/10 bg-white/60 p-5"
          >
            <h2 className="font-display text-2xl">Defaults</h2>
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Sun or shade</span>
              <select
                className="w-full rounded border border-ink/20 bg-white px-3 py-2"
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

            <label className="block text-sm">
              <span className="mb-1 block font-medium">Favorite area</span>
              <input
                className="w-full rounded border border-ink/20 bg-white px-3 py-2"
                value={prefs.favorite_areas[0] ?? ""}
                onChange={(e) =>
                  setPrefs({
                    ...prefs,
                    favorite_areas: [e.target.value.trim() || "Riva"],
                  })
                }
              />
            </label>

            <label className="block text-sm">
              <span className="mb-1 block font-medium">Default time</span>
              <select
                className="w-full rounded border border-ink/20 bg-white px-3 py-2"
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

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={prefs.avoid_busy}
                onChange={(e) =>
                  setPrefs({ ...prefs, avoid_busy: e.target.checked })
                }
              />
              Prefer less busy spots (Foursquare)
            </label>

            <button
              type="submit"
              className="rounded-full border border-ink px-5 py-2 text-xs font-medium uppercase tracking-widest hover:bg-ink hover:text-bone"
            >
              Save defaults
            </button>
            {status ? <p className="text-sm text-ink/70">{status}</p> : null}
          </form>

          <form
            onSubmit={onNotificationSubmit}
            className="space-y-5 rounded-3xl border border-terracotta-deep/20 bg-white/70 p-5"
          >
            <div>
              <h2 className="font-display text-2xl">Email notifications</h2>
              <p className="mt-1 text-sm text-ink/60">
                Pick the days and local time for a fresh Split cafe digest.
              </p>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={schedule.enabled}
                onChange={(e) =>
                  setSchedule({ ...schedule, enabled: e.target.checked })
                }
              />
              Send scheduled cafe picks
            </label>

            <div className="text-sm">
              <span className="mb-2 block font-medium">Days</span>
              <div className="flex flex-wrap gap-2">
                {weekdays.map((day) => {
                  const selected = schedule.days_of_week.includes(day.value);
                  return (
                    <button
                      key={day.value}
                      type="button"
                      className={`rounded-full border px-3 py-1 text-xs font-medium ${
                        selected
                          ? "border-terracotta-deep bg-terracotta-deep text-bone"
                          : "border-ink/20 bg-white text-ink"
                      }`}
                      onClick={() => toggleDay(day.value)}
                    >
                      {day.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Send time</span>
                <input
                  type="time"
                  className="w-full rounded border border-ink/20 bg-white px-3 py-2"
                  value={schedule.send_time_local}
                  onChange={(e) =>
                    setSchedule({
                      ...schedule,
                      send_time_local: e.target.value,
                    })
                  }
                />
              </label>

              <label className="block text-sm">
                <span className="mb-1 block font-medium">Area</span>
                <select
                  className="w-full rounded border border-ink/20 bg-white px-3 py-2"
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

              <label className="block text-sm">
                <span className="mb-1 block font-medium">Window</span>
                <select
                  className="w-full rounded border border-ink/20 bg-white px-3 py-2"
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

              <label className="block text-sm">
                <span className="mb-1 block font-medium">Preference</span>
                <select
                  className="w-full rounded border border-ink/20 bg-white px-3 py-2"
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
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                className="rounded-full border border-ink px-5 py-2 text-xs font-medium uppercase tracking-widest hover:bg-ink hover:text-bone"
              >
                Save notifications
              </button>
              <button
                type="button"
                className="rounded-full border border-terracotta-deep px-5 py-2 text-xs font-medium uppercase tracking-widest text-terracotta-deep hover:bg-terracotta-deep hover:text-bone"
                onClick={sendTestEmail}
              >
                Send test email
              </button>
            </div>
            {notificationStatus ? (
              <p className="text-sm text-ink/70">{notificationStatus}</p>
            ) : null}
          </form>
        </div>
      )}
    </main>
  );
}

function SettingsTitle() {
  return (
    <div>
      <Link href="/" className="text-sm text-terracotta-deep hover:underline">
        ← Back to app
      </Link>
      <h1 className="font-display mt-2 text-3xl">Your preferences</h1>
    </div>
  );
}
