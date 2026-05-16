# Follow the Shade - Implementation Summary

This document records what has been implemented in this repo and what should be built next. The current goal is a hackathon-ready MVP: a conversational Split cafe finder where the user asks naturally and the frontend renders map-ready cafe/shade data from `map_payload`.

## Source Material Used

- Read the project instructions in `AGENTS.md`.
- Read `Backend_Chatbot_And_API_Integrations.md`.
- Read the local Next 16 docs under `node_modules/next/dist/docs/` before adding route handlers.
- Copied/adapted backend structure and chat shell patterns from:

```text
C:\Users\roko.cubric\projekti\AI
```

The `AI` repo was readable. Two pytest cache folders denied access, but all relevant source files, tests, config, `agent.html`, and handoff docs were accessible.

## Implemented: Environment And Project Setup

- Added `.env.example` with the expected backend/frontend environment variables.
- Added local `.env` for development secrets and toggles. This file is ignored by git.
- Updated `.gitignore` so `.env.example` can be committed while real `.env` files stay ignored.
- Added Python project metadata in `pyproject.toml`.
- Added `uv.lock` through `uv run` dependency resolution.
- Added `agent_config.yaml` as a lightweight Follow the Shade agent config placeholder.
- Added `tzdata` for reliable `Europe/Zagreb` timezone support on Windows.

## Implemented: Python Backend

The Python backend lives under `src/` and follows the FastAPI structure copied from the `AI` project.

- Added FastAPI app entrypoint: `src/app/main.py`.
- Added app lifecycle wiring: `src/app/lifespan.py`.
- Added app container state: `src/app/state.py`.
- Added backend settings: `src/core/config.py`.
- Added logging setup copied/adapted from the AI repo: `src/core/logging_config.py`.
- Added chat API package: `src/app/api/chat/`.
- Added backend analysis persistence: `src/app/analysis_store.py`.
- Added domain agent facade: `src/services/follow_the_shade/agent.py`.
- Added cache-aware backend source scaffolding: `src/services/follow_the_shade/cache.py` and `src/services/follow_the_shade/data_sources.py`.
- Added composite tool: `src/tools/find_split_cafe_sun_shade_tool.py`.

Implemented backend endpoints:

- `GET /health`
- `GET /`
- `POST /chat/final_answer`
- `GET /chat/analysis/{analysis_id}`
- `POST /chat/speech/stt-key`
- `POST /chat/speech/tts-key`

## Implemented: Chat Contract

`POST /chat/final_answer` accepts both `message` and `query` for compatibility with the Next frontend and the old `AI/agent.html` pattern.

Example request:

```json
{
  "message": "Find me a shady cafe outside near Riva today from 3 to 5pm.",
  "thread_id": "stable-session-id",
  "include_audio": false
}
```

Example response shape:

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

Important frontend rule:

- Render assistant prose from `answer`.
- Render markers, result cards, timelines, and cafe metadata from `map_payload`.
- Do not parse cafe names or coordinates out of assistant prose.

## Implemented: Deterministic MVP Agent

The current Python agent is deterministic and seed-backed so it works before API keys and real geospatial services are connected.

Implemented behavior:

- Parses exposure preference:
  - `sun`
  - `shade`
  - `either`
- Parses supported Split areas:
  - Riva
  - Diocletian Palace / Pjaca
  - Marmontova
  - Prokurative
  - Matejuska
  - Varos
  - Bacvice
  - Firule
  - Znjan
  - West Coast
  - Sustipan
- Defaults unresolved location to central Split/Riva.
- Rejects outside-Split examples like Zagreb/Tkalciceva with a Split-focused clarification.
- Parses simple time windows:
  - `today from 3 to 5pm`
  - `tomorrow morning`
  - `this Saturday afternoon`
  - `lunch`
- Uses `Europe/Zagreb` runtime time.
- Asks one concise clarification when time is missing.
- Ranks seeded cafes by a blend of exposure match and locality.
- Persists every successful analysis under `analysis_id`.
- Recovers saved analyses through `GET /chat/analysis/{analysis_id}`.
- Uses `FOLLOW_THE_SHADE_DATA_MODE=mock|actual` to switch between seed-only development and server-side API attempts.
- Uses an in-memory TTL cache for repeated place, building, weather, and source-template lookups.

## Implemented: Seed Cafe Data

Added `assets/split_cafe_seed.json` with demo terrace points and exposure patterns.

The seed includes example cafes around:

- Riva
- Diocletian Palace
- Marmontova
- Prokurative
- Matejuska
- Bacvice
- Varos
- Znjan

The seed data currently powers both the Python backend and the Next mock backend.

## Implemented: Next Backend-For-Frontend Layer

Added Next route handlers that preserve the same frontend-facing contract.

Routes:

- `POST /chat/final_answer`
- `GET /chat/analysis/[analysis_id]`
- `POST /chat/speech/stt-key`
- `POST /chat/speech/tts-key`
- Matching `/api/chat/...` aliases

Behavior:

- If `FOLLOW_THE_SHADE_USE_MOCK=true`, Next returns its local deterministic mock response.
- If `FOLLOW_THE_SHADE_USE_MOCK=false` and `FOLLOW_THE_SHADE_API_BASE_URL` is set, Next proxies to the Python backend.
- This lets the frontend always call `/chat/final_answer`, regardless of whether it is using the mock or Python backend.

Backend data mode is separate from the Next proxy toggle:

- `FOLLOW_THE_SHADE_DATA_MODE=mock` keeps the Python backend on seed data for frontend development.
- `FOLLOW_THE_SHADE_DATA_MODE=actual` lets the Python backend attempt Google Places, Overpass, and Open-Meteo calls, while falling back to seed data and honest `source_notes` when inputs are missing.
- `FOLLOW_THE_SHADE_CACHE_TTL_SECONDS` controls the current in-memory upstream cache TTL.

Key files:

- `lib/follow-the-shade/types.ts`
- `lib/follow-the-shade/demo-backend.ts`
- `lib/follow-the-shade/route-handlers.ts`
- `app/chat/final_answer/route.ts`
- `app/chat/analysis/[analysis_id]/route.ts`
- `app/api/chat/final_answer/route.ts`
- `app/api/chat/analysis/[analysis_id]/route.ts`

## Implemented: Frontend Examples

### Next React Demo

Added a working React demo in:

```text
app/components/chatbot-demo.tsx
```

It demonstrates:

- Stable `thread_id` per session.
- Sending `{ message, thread_id, include_audio }`.
- Rendering chat messages.
- Rendering `map_payload.results`.
- Rendering simple marker positions.
- Rendering sample sun/shade timelines.
- Keeping cafe data separate from `answer` text.

The main page now loads this demo from:

```text
app/page.tsx
```

### Plain HTML Reference

Added:

```text
public/agent-reference.html
```

This is a lightweight Follow the Shade version of the `AI/agent.html` shell. It is meant as a visual and behavioral reference for the frontend developer.

It demonstrates:

- Chat-first UI.
- Language chips.
- Quick prompts.
- `POST /chat/final_answer` call pattern.
- Stable `thread_id`.
- Rendering `answer`.
- Rendering `map_payload` into markers and result cards.
- Timeline bars for sun/shade exposure samples.

Open it at:

```text
http://localhost:3000/agent-reference.html
```

## Implemented: Soniox Route Shape

The Python backend includes Soniox-compatible temporary-key endpoints copied/adapted from the AI repo.

Implemented:

- `POST /chat/speech/stt-key`
- `POST /chat/speech/tts-key`
- Split cafe speech context terms:
  - Follow the Shade
  - Split
  - Riva
  - Bacvice
  - Marmontova
  - Diocletian Palace
  - Pjaca
  - Prokurative
  - Matejuska
  - Varos
  - Firule
  - Znjan
  - shade
  - sunny terrace
  - outdoor seating

Notes:

- Real temporary-key generation requires `SONIOX_API_KEY`.
- Next mock speech endpoints intentionally return `501` while `FOLLOW_THE_SHADE_USE_MOCK=true`.
- Main Soniox keys stay server-side.

## Implemented: Documentation

Updated or added:

- `IMPLEMENTATION_SUMMARY.md`
- `BACKEND.md`
- `.env.example`

`BACKEND.md` remains the source-of-truth backend research doc. A current implementation status section was appended without deleting the original research notes.

## How To Run The Whole Project

Terminal 1, run Python backend:

```powershell
uv run uvicorn app.main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

Terminal 2, run Next:

```powershell
npm run dev
```

To make Next call Python, set this in `.env` and restart Next:

```env
FOLLOW_THE_SHADE_USE_MOCK=false
FOLLOW_THE_SHADE_API_BASE_URL=http://127.0.0.1:8000
```

To keep Python itself on deterministic seed data while the frontend develops, use:

```env
FOLLOW_THE_SHADE_DATA_MODE=mock
```

To exercise server-side API templates, use:

```env
FOLLOW_THE_SHADE_DATA_MODE=actual
FOLLOW_THE_SHADE_CACHE_TTL_SECONDS=600
```

Useful URLs:

- Next app: `http://localhost:3000`
- Frontend HTML reference: `http://localhost:3000/agent-reference.html`
- Python backend health: `http://127.0.0.1:8000/health`
- Python API docs: `http://127.0.0.1:8000/docs`

If port `8000` is already occupied:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Stop-Process -Id <OwningProcess> -Force
```

Or run backend on another port:

```powershell
uv run uvicorn app.main:app --app-dir src --reload --host 127.0.0.1 --port 8001
```

Then update `.env`:

```env
FOLLOW_THE_SHADE_API_BASE_URL=http://127.0.0.1:8001
```

## Verification Completed

Python:

```bash
uv run pytest
```

Result:

- 4 tests passed.

Frontend:

```bash
npm run lint
npm run build
```

Result:

- ESLint passed.
- Next production build passed.

Manual backend checks:

- `GET /health` returns healthy service status.
- `POST /chat/final_answer` returns `answer`, `analysis_id`, and `map_payload`.
- `GET /chat/analysis/{analysis_id}` returns the saved payload.
- Outside-Split request redirects back to Split.
- Missing-time request asks a clarification.

## Known Current Limitations

- The shade/sun result is currently seed-backed, not real geometric shadow analysis.
- Google Places Nearby Search has a first backend template in `actual` mode, but outdoor seating evidence and terrace points still degrade to seed/estimated data.
- OSM/Overpass building summary has a first backend template in `actual` mode, but building polygons are not yet used for real shadows.
- No Astral/Shapely shadow engine is connected yet.
- Open-Meteo weather summary has a first backend template in `actual` mode; mock mode still leaves weather values as `null`.
- Cafe terrace coordinates are estimates from `assets/split_cafe_seed.json`.
- Opening hours are assumed true for MVP seed results; Google `openNow` is only used when actual Places data is available.
- `map_payload.weather.cloud_cover_avg` and `precipitation_probability_max` remain `null` in mock mode.
- The current frontend map is a placeholder/pseudo-map, not Mapbox.
- The Python backend does not yet use LangGraph/OpenAI orchestration. It calls the composite tool directly for reliability.
- The current answer text includes source-aware uncertainty phrasing so we do not over-promise real analysis.
- The cache is in-memory per Python process; use Redis later if multiple backend instances are deployed.

## Planned Next: Backend

Highest priority backend tasks:

- Harden Google Places Nearby Search normalization and add tests for partial/malformed responses.
- Use `GOOGLE_MAPS_API_KEY` only on the server.
- Add OSM/Overpass fallback cafe search.
- Extend Overpass building fetch from summary counts to real footprint polygons.
- Add OSM height parsing:
  - `height`
  - `building:height`
  - `building:levels * 3`
  - default fallback height
- Add metric projection for Split:
  - input/output: `EPSG:4326`
  - working CRS: `EPSG:32633`
- Add Astral sun position calculations.
- Add Shapely building-shadow geometry.
- Sample sun/shade every 20 to 30 minutes across the user window.
- Replace seed exposure patterns with real geometric direct-sun samples.
- Add confidence reasons for:
  - estimated terrace point
  - missing building heights
  - default building heights
  - unavailable building data
- Add Open-Meteo cloud cover and precipitation probability.
- Persist richer `AnalysisRecord` objects with parsed request details.
- Add an API-level cap on candidates and buildings for demo performance.
- Move upstream cache to Redis if deployment needs shared cache across workers.

## Planned Next: Agent Intelligence

- Add optional OpenAI/LangChain structured parsing for more complex user requests.
- Keep deterministic pipeline as the source of truth for geometry and ranking.
- Add strict parsed request schema:
  - `preference`
  - `location_text`
  - `center`
  - `radius_m`
  - `start`
  - `end`
  - `must_be_open`
  - `language`
- Add support for more relative time phrases:
  - sunset
  - early afternoon
  - late afternoon
  - evening, with sun-below-horizon handling
- Add Croatian/Italian/German/French/Slovenian phrasing improvements.
- Add final response generation that explains 2 to 4 best matches naturally while still returning typed `map_payload`.
- Add source attribution strings based on real providers used in a request.

## Planned Next: Frontend

- Replace pseudo-map with Mapbox GL.
- Render markers from `map_payload.results[].terrace_point`.
- Use `map_payload.map.center` and `map_payload.map.zoom`.
- Show result cards with:
  - cafe name
  - exposure summary
  - match score
  - rating
  - outdoor seating confidence
  - transition notes
- Add sun/shade timeline component from `exposure.samples[]`.
- Add subtle source notes from `map_payload.source_notes`.
- Add loading and empty states tuned for the demo.
- Keep chat as the primary UX.
- Do not add filter panels, sliders, or date-picker-first UX.
- Add mobile layout where chat and map stack cleanly.
- Add a polished Mediterranean visual style.
- Optional: add Mapbox shadow overlay only as visual validation, not as ranking source.

## Planned Next: Demo Readiness

- Confirm the three demo queries work end to end:
  - `Find me a shady cafe outside near Riva today from 3 to 5pm.`
  - `I want sun around Bacvice tomorrow morning.`
  - `Somewhere near Marmontova that is shaded this Saturday afternoon.`
- Prepare 8 to 12 high-confidence seed terrace points in Split.
- Add a fallback mode that keeps the demo working if Google/Overpass fail.
- Keep the walkthrough under 60 seconds.
- Freeze after submission except for critical bug fixes.

## Planned Next: Tests

Add backend tests for:

- Request parsing for `today`, `tomorrow`, and `this Saturday afternoon`.
- Outside-Split redirect behavior.
- `analysis_id` persistence and recovery.
- Google Places normalization.
- OSM building height parsing.
- Synthetic shadow geometry.
- Weather fetch normalization.
- `map_payload` contract stability.

Add frontend checks for:

- Chat request body shape.
- Rendering `map_payload` without parsing `answer`.
- Mobile layout.
- Empty and loading states.

## Handoff Notes For Frontend Developer

- Call `POST /chat/final_answer`.
- Send a stable `thread_id`.
- Send `include_audio: false` unless voice playback is being tested.
- Render assistant message from `answer`.
- Render all cafe and map UI from `map_payload`.
- Use `analysis_id` for reload/recovery.
- Use `GET /chat/analysis/{analysis_id}` to recover a saved analysis.
- Use `public/agent-reference.html` as a behavior reference, not final design.
- Use `app/components/chatbot-demo.tsx` as the React integration reference.

## Handoff Notes For Backend Developer

- Keep one composite tool: `find_split_cafe_sun_shade`.
- Do not let the LLM invent sun/shade.
- Keep geometry deterministic.
- Keep Split-only behavior strict.
- Keep secrets server-side.
- Keep `map_payload` stable so frontend and backend can work in parallel.
