# Follow the Shade

Follow the Shade is a Split-only outdoor cafe finder. Users ask naturally, for example: "Find me a shady cafe outside near Riva today from 3 to 5pm." The backend returns conversational advice plus a typed `map_payload` that the frontend renders as map markers, result cards, and sun/shade timelines.

## Architecture

```text
Next.js frontend
	-> POST /chat/final_answer
	-> FastAPI backend
	-> FollowTheShadeAgent
	-> find_split_cafe_sun_shade composite tool
	-> map_payload + analysis_id
```

The MVP keeps one agent and one deterministic tool. External APIs sit behind cache-aware source templates so frontend development can use mock data without paying for or waiting on real calls.

## Modes

There are two separate toggles:

| Variable                            | Layer               | Use                                                                         |
| ----------------------------------- | ------------------- | --------------------------------------------------------------------------- |
| `FOLLOW_THE_SHADE_USE_MOCK=true`    | Next route handlers | Return the local TypeScript mock response.                                  |
| `FOLLOW_THE_SHADE_USE_MOCK=false`   | Next route handlers | Proxy `/chat/...` routes to FastAPI.                                        |
| `FOLLOW_THE_SHADE_DATA_MODE=mock`   | Python backend      | Use seed cafe data and mocked weather/building notes.                       |
| `FOLLOW_THE_SHADE_DATA_MODE=actual` | Python backend      | Attempt Google Places, Overpass, and Open-Meteo calls, with seed fallbacks. |

Default for frontend work:

```env
FOLLOW_THE_SHADE_USE_MOCK=true
FOLLOW_THE_SHADE_DATA_MODE=mock
```

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
```

`GOOGLE_PLACES_API_KEY` is the preferred server-side key for Google Places calls. If it is unset, the backend falls back to `GOOGLE_MAPS_API_KEY`.

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
  "message": "Find me a shady cafe outside near Riva today from 3 to 5pm.",
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

Frontend rule: render cafe names, coordinates, scores, and timelines only from `map_payload`. Do not parse assistant prose for cafe data.

## Fallbacks

The backend should degrade gracefully:

- Missing or failed Google Places: seed cafes now, OSM cafe fallback later.
- Few cafes with outdoor evidence: supplement with seed/OSM and lower `outdoor_seating.confidence`.
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
