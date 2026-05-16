# Follow the Shade - Backend Builder Handoff

## What was done

- Read `Backend_Chatbot_And_API_Integrations.md` and the local Next 16 route/environment docs under `node_modules/next/dist/docs/`.
- Added env scaffolding:
  - `.env` for local secrets and toggles.
  - `.env.example` for teammates.
  - `.gitignore` now allows `.env.example` to be tracked while keeping real `.env` files ignored.
- Added a minimal contract-compatible chatbot backend inside Next route handlers:
  - `POST /chat/final_answer`
  - `GET /chat/analysis/[analysis_id]`
  - `POST /chat/speech/stt-key`
  - `POST /chat/speech/tts-key`
  - Matching `/api/chat/...` aliases are also available for Next-style callers.
- Added shared response/data contracts in `lib/follow-the-shade/types.ts`.
- Added an in-memory demo analysis store and deterministic seed-backed response builder in `lib/follow-the-shade/demo-backend.ts`.
- Added `assets/split_cafe_seed.json` with Split demo terrace points and exposure samples.
- Replaced the starter Next page with a small chatbot example in `app/components/chatbot-demo.tsx`.
- Rebranded the app metadata and base styling to Follow the Shade.
- Added a Python FastAPI backend copied/adapted from `C:\Users\roko.cubric\projekti\AI`:
  - `src/app/main.py`, `src/app/lifespan.py`, `src/app/state.py`
  - `src/app/api/chat/routes.py`, `src/app/api/chat/schemas.py`
  - `src/app/analysis_store.py`
  - `src/tools/find_split_cafe_sun_shade_tool.py`
  - `src/services/follow_the_shade/agent.py`
- Added `public/agent-reference.html`, a lightweight Follow the Shade version of the old `AI/agent.html` shell for the frontend developer.

## Source repo note

The backend and reference chat shell were copied/adapted from:

```text
C:\Users\roko.cubric\projekti\AI
```

Two pytest cache folders in that repo had access denied, but the source files, tests, config, and `agent.html` were readable.

## How the current chatbot works

The demo endpoint accepts:

```json
{
  "message": "Find me a shady cafe outside near Riva today from 3 to 5pm.",
  "thread_id": "stable-session-id",
  "include_audio": false
}
```

It returns:

```json
{
  "answer": "Assistant prose",
  "thread_id": "stable-session-id",
  "analysis_id": "shade_...",
  "map_payload": {},
  "sources": [],
  "audio": null,
  "detected_language": "en"
}
```

The frontend should render cafe/map data only from `map_payload`, not by parsing `answer`.

## Running the Python backend

Use this backend during local integration:

```bash
uv run uvicorn app.main:app --app-dir src --reload --port 8000
```

Then point Next at it:

```bash
FOLLOW_THE_SHADE_API_BASE_URL=http://localhost:8000
FOLLOW_THE_SHADE_USE_MOCK=false
```

## Switching Next to the Python backend

When the FastAPI backend is running:

1. Put its base URL in `.env`:

```bash
FOLLOW_THE_SHADE_API_BASE_URL=http://localhost:8000
FOLLOW_THE_SHADE_USE_MOCK=false
```

2. Keep calling the same frontend endpoint:

```text
POST /chat/final_answer
```

The Next route will proxy to:

```text
POST {FOLLOW_THE_SHADE_API_BASE_URL}/chat/final_answer
```

## Speech endpoints

The Next speech-key endpoints return `501` while `FOLLOW_THE_SHADE_USE_MOCK=true`. The Python backend has the copied Soniox temporary-key route shape and will create real temporary keys once `SONIOX_API_KEY` is filled.

## Next steps

- Add real Google Places / OSM / Open-Meteo / shadow-engine services in the backend.
- Let the frontend teammate replace the placeholder pseudo-map with Mapbox rendering from `map_payload`.
