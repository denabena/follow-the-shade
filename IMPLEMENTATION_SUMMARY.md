# Follow the Shade - Implementation Summary

This document records what has been implemented in this repo and what should be built next. The current goal is a hackathon-ready MVP: a conversational Split cafe finder where the user asks naturally and the frontend renders map-ready cafe/shade data from `map_payload`.

## Current Status

As of merge commit `4dbde8d` on `main`:

- The two real `origin/main` commits (`2fb6dc9` and `1fcc57a`) are merged into this repo and pushed.
- The frontend now uses the Studio experience in `components/Studio.tsx`, not the older chat demo shell.
- The backend shading pipeline from `origin/main` is wired into the cache-aware mock/actual data-source layer added locally.
- `FOLLOW_THE_SHADE_DATA_MODE=mock` keeps backend responses deterministic with seed cafes and seed exposure patterns.
- `FOLLOW_THE_SHADE_DATA_MODE=actual` now runs the real Overpass/Open-Meteo/Google Places path and geometric shade analysis.
- Verification passed with `uv lock`, `uv run pytest`, `npm run lint`, and `npm run build`.

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
- Added parsed-request and ranking pipeline: `src/services/follow_the_shade/pipeline.py`.
- Added provider/service integrations under:
  - `src/services/geodata/`
  - `src/services/places/`
  - `src/services/shadow/`
  - `src/services/weather/`
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

## Implemented: Parsed Request And Shading Pipeline

The current backend is still deterministic in parsing, ranking, and response assembly, but it is no longer seed-only.

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
- Uses `FOLLOW_THE_SHADE_DATA_MODE=mock|actual` to switch between deterministic seed mode and server-side API attempts.
- Uses an in-memory TTL cache for repeated place, building, weather, and source-template lookups.
- In `mock` mode:
  - returns seed cafes from `assets/split_cafe_seed.json`
  - uses seed `patterns` as exposure samples
  - returns mocked building/weather notes so the frontend can develop deterministically
- In `actual` mode:
  - fetches cafe candidates from Google Places when configured
  - fetches building footprints and outdoor seating from Overpass
  - fetches cloud cover / precipitation context from Open-Meteo
  - computes direct sun/shade samples with Astral, Shapely, and `pyproj`
- Ranks cafes by a blend of exposure match, locality, and rating.
- Persists every successful analysis under `analysis_id`.
- Recovers saved analyses through `GET /chat/analysis/{analysis_id}`.
- Keeps Split-only redirect behavior and one-question clarification behavior intact.

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

The seed file now also preserves `patterns` for the extra Riva cafes added from `origin/main`, so it remains usable for both the Studio frontend mock flow and backend mock mode.

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

## Implemented: Frontend Studio UI

The primary frontend experience now lives in:

```text
components/Studio.tsx
```

The main page loads it from:

```text
app/page.tsx
```

Implemented frontend behavior:

- Stable `thread_id` per session.
- Chat-first split layout with chat on one side and the map on the other.
- Suggestion chips for the core demo queries.
- Streaming bot message rendering.
- Result cards built from `map_payload`, not from `answer` parsing.
- Timeline bars built from backend exposure samples.
- Map marker focus/fly-to behavior for selected cafes.
- Mapbox GL map panel with custom marker rendering.
- Optional client-side ShadeMap overlay support when runtime keys are present.
- Runtime handling for missing or invalid map tokens.

Key frontend files:

- `components/Studio.tsx`
- `components/ChatPanel.tsx`
- `components/MapPanel.tsx`
- `components/CafeResultCard.tsx`
- `components/SunTimelineBar.tsx`
- `lib/backend.ts`
- `lib/map-payload-adapter.ts`
- `lib/types.ts`

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
- `README.md`

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

- `uv lock` completed successfully without changing `uv.lock`.
- 7 tests passed.

Frontend:

```bash
npm run lint
npm run build
```

Result:

- ESLint passed.
- Next production build passed.
- The build was re-run after stopping local dev processes that were holding a `.next` log file open.

Manual backend checks:

- `GET /health` returns healthy service status.
- `POST /chat/final_answer` returns `answer`, `analysis_id`, and `map_payload`.
- `GET /chat/analysis/{analysis_id}` returns the saved payload.
- Outside-Split request redirects back to Split.
- Missing-time request asks a clarification.

## Known Current Limitations

- `mock` mode is still seed/pattern-backed by design; it does not use live geometry or live weather.
- `actual` mode now uses real geometric shadow analysis, but the result quality still depends heavily on OSM building completeness and terrace-point estimates.
- Google Places Nearby Search is integrated, but outdoor seating evidence and open-for-window handling are still coarse.
- There is still no OSM cafe fallback when Google Places returns poor or empty candidate sets.
- Overpass building coverage is usable for MVP shading, but relation-heavy/malformed footprint cases still need hardening.
- Building heights are often estimated from levels or default values, which lowers confidence.
- Cafe terrace coordinates are estimates from `assets/split_cafe_seed.json`.
- Opening hours are still assumed true for most MVP results; window-level open filtering is not enforced yet.
- `map_payload.weather.cloud_cover_avg` and `precipitation_probability_max` remain `null` in mock mode.
- The frontend map is now Mapbox-based, but the best experience still depends on valid Mapbox and optional ShadeMap runtime keys.
- `components/AnalysisOverlay.tsx` exists, but backend progress is not yet streamed into the UI.
- The frontend does not yet recover the previous analysis on reload via `analysis_id`.
- The Python backend does not yet use LangGraph/OpenAI orchestration. It calls the composite tool directly for reliability.
- The current answer text includes source-aware uncertainty phrasing so we do not over-promise real analysis.
- The cache is in-memory per Python process; use Redis later if multiple backend instances are deployed.

## Planned Next: Backend

Highest priority backend tasks:

- Add OSM/Overpass fallback cafe search.
- Harden Google Places normalization and add tests for partial/malformed responses.
- Improve `is_open_for_window` logic instead of assuming `True` for most results.
- Improve terrace-point resolution when no explicit outdoor seating node is available.
- Harden Overpass footprint parsing and confidence handling for missing/malformed relations.
- Tune ranking and source-note wording when building heights are estimated or geometry is sparse.
- Persist richer `AnalysisRecord` metadata for reload/deep-link flows.
- Consider exposing backend progress if we want the analysis overlay to reflect real processing steps.
- Add confidence reasons for:
  - estimated terrace point
  - missing building heights
  - default building heights
  - unavailable building data
- Add Open-Meteo cloud cover and precipitation probability.
- Add an API-level cap on candidates and buildings for demo performance.
- Move upstream cache to Redis if deployment needs shared cache across workers.

## Planned Next: Agent Intelligence

- Keep deterministic pipeline as the source of truth for geometry and ranking.
- Add optional OpenAI/LangChain structured parsing for more complex follow-up requests.
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
- Add support for simple conversational follow-ups on the same thread:
  - “something closer to the sea”
  - “later”
  - “more shade”
- Add Croatian/Italian/German/French/Slovenian phrasing improvements.
- Add final response generation that explains 2 to 4 best matches naturally while still returning typed `map_payload`.
- Add source attribution strings based on real providers used in a request.

## Planned Next: Frontend

- Connect reload/deep-link recovery using `analysis_id` and `GET /chat/analysis/{analysis_id}`.
- Surface source notes and confidence more clearly in the Studio UI.
- Decide whether to wire `AnalysisOverlay` to real backend progress or remove it from the shipped surface.
- Add loading and empty states tuned for the demo.
- Keep chat as the primary UX.
- Do not add filter panels, sliders, or date-picker-first UX.
- Add mobile layout where chat and map stack cleanly.
- Add a polished Mediterranean visual style.
- Optional: keep the client-side ShadeMap overlay only as visual validation, never as ranking source.
- Add frontend tests around `lib/map-payload-adapter.ts`, Studio interactions, and error states.

## Planned Next: Demo Readiness

- Confirm the three demo queries work end to end:
  - `Find me a shady cafe outside near Riva today from 3 to 5pm.`
  - `I want sun around Bacvice tomorrow morning.`
  - `Somewhere near Marmontova that is shaded this Saturday afternoon.`
- Rehearse those three queries in both `mock` mode and `actual` mode.
- Keep 8 to 12 high-confidence seed terrace points in Split as the fallback runbook.
- Add a fallback mode that keeps the demo working if Google/Overpass fail.
- Verify the map/token setup on the demo machine before recording.
- Keep the walkthrough under 60 seconds.
- Freeze after submission except for critical bug fixes.

## Planned Next: Tests

Add backend tests for:

- Google Places normalization.
- Mock mode seed-pattern exposure and `source_notes` behavior.
- OSM building height parsing.
- Overpass outdoor seating fallback and relation parsing.
- Synthetic shadow geometry.
- Weather fetch normalization.
- `map_payload` contract stability.
- Request parsing for `today`, `tomorrow`, and `this Saturday afternoon`.
- Outside-Split redirect behavior.
- `analysis_id` persistence and recovery.

Add frontend checks for:

- Chat request body shape.
- Rendering `map_payload` without parsing `answer`.
- Studio result-card rendering from real backend payloads.
- Analysis reload/recovery flow.
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
- Use `components/Studio.tsx` as the current React integration reference.
- Use `lib/map-payload-adapter.ts` as the adapter layer between backend payloads and frontend UI types.

## Handoff Notes For Backend Developer

- Keep one composite tool: `find_split_cafe_sun_shade`.
- Do not let the LLM invent sun/shade.
- Keep geometry deterministic.
- Keep Split-only behavior strict.
- Keep secrets server-side.
- Keep `map_payload` stable so frontend and backend can work in parallel.
- Keep `mock` mode deterministic and fast, even as `actual` mode gets smarter.
