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

## Important caveat

The requested `AI/` repo and BINA Istra chatbot files were not present in this workspace or nearby folders, so no files could be copied directly. This implementation follows the handoff contract from `Backend_Chatbot_And_API_Integrations.md` and gives the frontend teammate a working shape to integrate against.

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

## Switching to the real backend later

When the FastAPI/LangChain backend exists:

1. Put its base URL in `.env`:

```bash
FOLLOW_THE_SHADE_API_BASE_URL=http://localhost:8000
FOLLOW_THE_SHADE_USE_MOCK=false
```

2. Keep calling the same frontend endpoint:

```text
POST /chat/final_answer
```

The Next route will proxy to the real backend path:

```text
POST {FOLLOW_THE_SHADE_API_BASE_URL}/chat/final_answer
```

## Speech endpoints

The Soniox speech-key endpoints are present but intentionally return `501` while `FOLLOW_THE_SHADE_USE_MOCK=true`. Temporary key creation should happen in the real backend so main Soniox keys never reach browser code.

## Next steps

- Replace the demo seed response with the real composite tool pipeline.
- Add real Google Places / OSM / Open-Meteo / shadow-engine services in the backend.
- Let the frontend teammate replace the placeholder pseudo-map with Mapbox rendering from `map_payload`.
