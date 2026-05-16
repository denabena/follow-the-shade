"use client";

import { UserButton } from "@clerk/nextjs";
import { FormEvent, useEffect, useState } from "react";

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

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<Preferences>(defaultPrefs);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch("/api/me/preferences");
        if (response.ok) {
          setPrefs((await response.json()) as Preferences);
        }
      } finally {
        setLoading(false);
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

  return (
    <main className="mx-auto max-w-lg px-6 py-10 text-ink">
      <header className="mb-8 flex items-center justify-between">
        <SettingsTitle />
        <UserButton />
      </header>
      {loading ? (
        <p className="text-sm text-ink/60">Loading…</p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-5">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Sun or shade</span>
            <select
              className="w-full rounded border border-ink/20 bg-white px-3 py-2"
              value={prefs.exposure_preference}
              onChange={(e) =>
                setPrefs({
                  ...prefs,
                  exposure_preference: e.target.value as Preferences["exposure_preference"],
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
                  default_time_preset: e.target.value as Preferences["default_time_preset"],
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

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={prefs.digest_enabled}
              onChange={(e) =>
                setPrefs({ ...prefs, digest_enabled: e.target.checked })
              }
            />
            Daily digest (coming soon)
          </label>

          <button
            type="submit"
            className="rounded-full border border-ink px-5 py-2 text-xs font-medium uppercase tracking-widest hover:bg-ink hover:text-bone"
          >
            Save
          </button>
          {status ? <p className="text-sm text-ink/70">{status}</p> : null}
        </form>
      )}
    </main>
  );
}

function SettingsTitle() {
  return (
    <div>
      <a href="/" className="text-sm text-terracotta-deep hover:underline">
        ← Back to app
      </a>
      <h1 className="font-display mt-2 text-3xl">Your preferences</h1>
    </div>
  );
}
