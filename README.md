# Follow the Shade

Follow the Shade is a Split-only outdoor venue finder for cafes, restaurants, bars, nightclubs, and similar terraces. Users ask naturally, for example: "Find me a shady restaurant outside near Riva today from 3 to 5pm." The backend returns conversational advice plus a typed `map_payload` that the frontend renders as map markers, result cards, and sun/shade timelines.

## Architecture

```text
Next.js frontend
	-> POST /chat/final_answer
	-> FastAPI backend
  -> LangGraph Follow the Shade agent
  -> find_split_cafe_sun_shade composite tool
	-> map_payload + analysis_id
```

The MVP keeps one LangGraph chat agent and one deterministic analysis tool. External APIs sit behind cache-aware source templates so frontend development can use mock data without paying for or waiting on real calls. Python chat requires `OPENAI_API_KEY`; the deterministic pipeline is exposed to the agent as a tool and is reused by scheduled notification digests.

## Modes

There are two separate toggles:

| Variable                            | Layer               | Use                                                                         |
| ----------------------------------- | ------------------- | --------------------------------------------------------------------------- |
| `FOLLOW_THE_SHADE_USE_MOCK=true`    | Next route handlers | Return the local TypeScript mock response.                                  |
| `FOLLOW_THE_SHADE_USE_MOCK=false`   | Next route handlers | Proxy `/chat/...` routes to FastAPI.                                        |
| `FOLLOW_THE_SHADE_DATA_MODE=mock`   | Python backend      | Use seed venue data and mocked weather/building notes.                      |
| `FOLLOW_THE_SHADE_DATA_MODE=actual` | Python backend      | Attempt Google Places, Overpass, and Open-Meteo calls, with seed fallbacks. |

Default for frontend work:

```env
FOLLOW_THE_SHADE_USE_MOCK=true
FOLLOW_THE_SHADE_DATA_MODE=mock
```

Local development values usually live in `.env.local`. The Next app reads that file automatically, and the Python backend reads both `.env` and `.env.local`, with `.env.local` taking precedence.

Proxy Next to Python while keeping deterministic backend data:

```env
FOLLOW_THE_SHADE_USE_MOCK=false
FOLLOW_THE_SHADE_API_BASE_URL=http://127.0.0.1:8000
FOLLOW_THE_SHADE_DATA_MODE=mock
```

Exercise backend API templates:

```env
FOLLOW_THE_SHADE_USE_MOCK=false
FOLLOW_THE_SHADE_API_BASE_URL=http://127.0.0.1:8000
FOLLOW_THE_SHADE_DATA_MODE=actual
FOLLOW_THE_SHADE_CACHE_TTL_SECONDS=600
GOOGLE_PLACES_API_KEY=
OPENAI_API_KEY=
```

`GOOGLE_PLACES_API_KEY` is the preferred server-side key for Google Places calls. If it is unset, the backend falls back to `GOOGLE_MAPS_API_KEY`.

## Email Notifications

Users can schedule recurring email digests from Settings. The FastAPI process runs an in-process APScheduler loop, reuses the existing shade pipeline, and sends through Resend.

```env
RESEND_API_KEY=
RESEND_FROM_EMAIL=Follow the Shade <noreply@example.com>
CLERK_SECRET_KEY=
NOTIFICATIONS_ENABLED=false
NOTIFICATIONS_DRY_RUN=true
NOTIFICATIONS_CHECK_INTERVAL_SECONDS=60
NOTIFICATIONS_SCHEDULES_PATH=data/notification_schedules.json
```

Local dry-run demo:

1. Set `FOLLOW_THE_SHADE_DATA_MODE=mock`, `NOTIFICATIONS_ENABLED=true`, and `NOTIFICATIONS_DRY_RUN=true`.
2. Sign in, open Settings, enable notifications, then pick days, time, area, window, and sun/shade preference.
3. Click "Send test email" to render the email in backend logs without calling Resend.
4. Set `NOTIFICATIONS_DRY_RUN=false` and provide `RESEND_API_KEY` to send real email.

Before production, add unsubscribe links and move schedules to a shared database if the backend runs more than one process.

## Run Locally

Install frontend dependencies:

```powershell
npm install
```

Run the Python backend:

```powershell
uv run uvicorn app.main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

Run the Next app:

```powershell
npm run dev
```

Useful URLs:

- Next app: `http://localhost:3000`
- HTML reference: `http://localhost:3000/agent-reference.html`
- Backend health: `http://127.0.0.1:8000/health`
- Backend docs: `http://127.0.0.1:8000/docs`

## API Contract

Primary request:

```json
{
  "message": "Find me a shady restaurant outside near Riva today from 3 to 5pm.",
  "thread_id": "stable-session-id",
  "include_audio": false
}
```

Primary response:

```json
{
  "answer": "Assistant prose",
  "thread_id": "stable-session-id",
  "analysis_id": "shade_20260516_abcd1234",
  "map_payload": {},
  "sources": [],
  "audio": null,
  "detected_language": "en"
}
```

Frontend rule: render venue names, coordinates, scores, and timelines only from `map_payload`. Do not parse assistant prose for venue data.

## Fallbacks

The backend should degrade gracefully:

- Missing or failed Google Places: seed venues now, OSM venue fallback later.
- Few venues with outdoor evidence: supplement with seed/OSM and lower `outdoor_seating.confidence`.
- Missing building geometry: return results with lower exposure confidence.
- Missing building heights: use OSM `height`, then `building:levels * 3`, then 9m default once geometry is live.
- Missing weather: leave weather fields `null` and keep the answer focused on direct sun/shade.

See `BACKEND.md` for the full fallback and caching requirements.

## Verification

Backend tests:

```powershell
uv run pytest
```

Frontend checks:

```powershell
npm run lint
npm run build
```
