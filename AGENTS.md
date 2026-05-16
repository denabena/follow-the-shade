<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

<!-- END:nextjs-agent-rules -->

# Follow the Shade — Agent Playbook

**Follow the Shade** is a conversational Split outdoor venue finder. Users ask naturally — e.g. “I want a shady restaurant near Riva from 3 to 5 today” — and get map-ready results with real sun/shade analysis for cafes, restaurants, bars, nightclubs, and similar terraces. It should feel like a local friend checked the conditions, not a generic places search.

Full backend research and API notes live in `BACKEND.md`. This file is the operational guide for all agents.

---

## Hackathon North Star

Judges sit through 20+ pitches. Optimize for **one jaw-drop moment**, **polished design**, and **a demo that sells itself**.

| Principle             | What it means for agents                                                                                                                                                                                                      |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Be innovative**     | Lead with the wow: _real building-shadow analysis on Split terraces for a specific time window_ — not “another chatbot with a map.” Make the sun/shade transition visible (map markers, timeline samples, or shadow overlay). |
| **Design matters**    | Ugly kills credibility. Mediterranean warmth, clear typography, confident spacing. No filter panels — chat + map only. Polish beats features.                                                                                 |
| **Keep demo short**   | Record a **≤1 min** silent interactive walkthrough (no voiceover). Let the product speak. Rehearse these queries (see Demo Script).                                                                                           |
| **Keep pitch simple** | One line: _“Tell us where and when you want to sit outside in Split — we check which terraces are actually sunny or shaded.”_ Three beats: problem → magic moment → why only us.                                              |
| **Sell the idea**     | Copy and UI sell confidence and locality (“Split-only”, honest uncertainty). Never over-promise live occupancy or perfect terrace GPS.                                                                                        |
| **Be on time**        | **Freeze after submission.** No prod pushes or risky refactors before stage. Bug fixes only.                                                                                                                                  |

---

## Product Rules (Non-Negotiable)

- **City:** Split, Croatia only. Default unresolved location to Split, not Croatia generally.
- **Outside Split:** Gently redirect — “I’m focused on Split. Do you want something around Riva, Bačvice, Marmontova, Varoš, or another Split area?”
- **No Zagreb demos:** “Tkalčićeva” is Zagreb — do not seed Split data with it.
- **Good demo areas:** Riva, Diocletian’s Palace / Pjaca, Marmontova, Prokurative, Matejuška, Varoš, Bačvice, Firule, Žnjan, West Coast, Sustipan.
- **No filters in UI:** User chats; clarifying questions happen in chat. Map displays `map_payload` — never parse assistant prose for venue data.
- **Honest uncertainty:** Mention estimated terrace points, missing building heights, cloud cover, umbrellas/awnings not modeled — only when it affects the recommendation.

---

## Architecture

```text
User (voice or text)
    → Next.js frontend (this repo)
    → POST /chat/final_answer  (+ optional Soniox speech keys)
    → FastAPI + LangChain agent
    → find_split_cafe_sun_shade (one composite tool, deterministic pipeline)
    → analysis_id + map_payload back to frontend
```

**Frontend (this repo):** Next.js 16, React 19, Tailwind 4, Mapbox GL + `mapbox-gl-shadow-simulator` (optional visual overlay only — backend is source of truth for rankings).

**Backend (separate codebase per `BACKEND.md`):** FastAPI + LangChain/LangGraph, composite tool, Google Places + OSM Overpass, Astral + Shapely shadow engine, Open-Meteo cloud cover, Soniox STT/TTS.

---

## Wow Feature (Prioritize This)

**Geometric sun/shade across the user’s time window** on real Split venue terraces, ranked by preference (`sun` | `shade` | `either`), with weather nuance.

The demo moment: user asks for shade near Riva 15:00–17:00 → map shows 2–4 venues with exposure samples and a clear “mostly shaded / brief sun patch at 16:00” story.

Optional polish: Mapbox shadow simulator overlay for visual validation — never replace backend scores with frontend-only shadow checks.

---

## Frontend Agent Instructions

### Stack

- App Router under `app/`
- Read `node_modules/next/dist/docs/` before changing routing, data fetching, or config
- Dependencies already include `mapbox-gl` and `mapbox-gl-shadow-simulator`

### API contract (do not invent fields)

**Primary:** `POST /chat/final_answer`

```json
{
  "message": "user text",
  "thread_id": "stable-uuid-per-session",
  "include_audio": false
}
```

**Response fields to use:**

| Field         | Use                                                   |
| ------------- | ----------------------------------------------------- |
| `answer`      | Assistant prose in chat                               |
| `analysis_id` | Reload / deep-link recovery                           |
| `map_payload` | **Only** source for map markers, scores, time samples |
| `sources`     | Optional attribution list                             |
| `audio`       | When `include_audio=true`                             |

**Recovery:** `GET /chat/analysis/{analysis_id}` if the page reloads.

**Voice (optional layer):**

- `POST /chat/speech/stt-key` — browser mic (temporary Soniox key only)
- `POST /chat/speech/tts-key` — browser TTS
- Never put main Soniox/API keys in client code

### UI shape

- Split-screen or stacked: **chat** + **map** (map is hero on desktop)
- Render `map_payload.map.center`, `results[]` with `terrace_point`, `exposure.samples`, `exposure.summary`
- Show `source_notes` subtly (OSM, Google, Open-Meteo attribution)
- Multilingual tourists: support `detected_language` from backend when styling copy
- Mobile-first; demo must work on one laptop screen recording

### Do not

- Build filter sliders, date pickers, or “preference toggles” as primary UX
- Scrape venue names from `answer` text
- Block MVP on shadow overlay — text + markers + sample timeline is enough
- Ship generic “AI assistant” chrome — brand Follow the Shade

---

## Backend Agent Instructions

See `BACKEND.md` for file paths, API research, and implementation sketch. Summary:

### One composite tool

```text
find_split_cafe_sun_shade(query, thread_id) → JSON
```

Pipeline (deterministic — model explains, does not compute geometry):

1. Parse request → strict schema (`preference`, time window, Split location, `must_be_open`, etc.)
2. Geocode (Google Places or `SPLIT_LANDMARKS` seed dict for demo reliability)
3. Find venues with outdoor-seating evidence (Google Places; OSM Overpass fallback)
4. Fetch buildings + estimate heights (Overpass; default 9m when tags missing)
5. Shadow engine: Astral sun position + Shapely shadows in `EPSG:32633`
6. Open-Meteo `cloud_cover` for weather-adjusted phrasing
7. Persist `AnalysisRecord` → return `analysis_id` + `map_payload`

### Reuse existing chatbot codebase

Key touchpoints: `src/app/lifespan.py`, `tool_registry.py`, `src/tools/get_faq_info_tool.py` pattern, `src/app/api/chat/routes.py`, `generate_answer.py` (`extract_map_payload`), `agent_config.yaml`, Soniox endpoints in `routes.py`.

Extend `ChatResponse` with `analysis_id` and `map_payload`. Add `src/app/analysis_store.py`.

### Time and locale

- Inject current time as `Europe/Zagreb` into prompt/tool
- Defaults: afternoon → 14:00–18:00, morning → 09:00–12:00, lunch → 12:00–14:00
- Missing date/time → one concise clarifying question, not a form

### MVP caps (performance)

- ≤12 venue candidates; buildings within 350–500m; sample every 20–30 min
- Cache Overpass by bbox; do not poll Overpass from the browser

### Secrets

- All place/geocode/shadow keys stay server-side
- Do not paste `.env` values into docs, tests, or commits

---

## Parsed Request & Map Payload

Agents must keep contracts stable so frontend and backend can work in parallel.

**Parsed request** (internal): `preference`, `location_text`, `center`, `radius_m`, `start`, `end`, `must_be_open`, `language`.

**`map_payload`** (frontend renders this): `analysis_id`, `request`, `map.center`, `results[]` with `exposure.match_score`, `exposure.samples[]`, `exposure.summary`, `outdoor_seating.confidence`, `weather`, `source_notes`. Full example in `BACKEND.md` § Suggested Data Contracts.

**Tool return shape:**

```json
{
  "analysis_id": "...",
  "answer_facts": {
    "best_matches": [],
    "preference": "shade",
    "time_window_label": "...",
    "important_nuance": "..."
  },
  "map_payload": {}
}
```

---

## Agent Prompt Core (backend `agent_config.yaml`)

- Role: local Split assistant for outdoor venue sun/shade
- Call `find_split_cafe_sun_shade` exactly once when intent is clear
- Do not invent sun/shade — use tool output
- Final JSON only: `{ "response": "...", "detected_language": "hr|en|it|de|sl|fr" }`

---

## Demo Script (Rehearse These)

Silent walkthrough, ≤60s, no narration:

1. “Find me a shady restaurant outside near Riva today from 3 to 5pm.”
2. “I want sun around Bačvice tomorrow morning.”
3. “Somewhere near Marmontova that is shaded this Saturday afternoon.”

Prepare `assets/split_cafe_seed.json` (8–12 known venue terraces) if APIs or terrace detection are flaky during the live demo.

---

## Build Priority (9-Hour MVP)

1. Rebrand config/prompt → Follow the Shade
2. Soniox STT context terms (Split/venue/sun); keep speech endpoints
3. `analysis_id` + `map_payload` on chat response + `AnalysisStore`
4. Google Places (or OSM fallback) + Overpass buildings + shadow engine
5. Frontend: chat + map from `map_payload` only
6. Open-Meteo cloud cover phrasing
7. Terrace confidence + seed venue overrides
8. **Freeze** — optional: busyness, Foursquare, shadow overlay

---

## Pitch Cheat Sheet (For Humans, Not Code)

- **Hook:** “Where do you sit outside in Split without guessing sun or shade?”
- **Proof:** Live query → map pins with “shaded 15:00–17:00, brief sun at 16:00”
- **Moat:** Building geometry + time window — not Google “open now”
- **Close:** “Split-only today; every Adriatic terrace city next.”

---

## Source of Truth

| Topic                                            | Document                       |
| ------------------------------------------------ | ------------------------------ |
| API research, file list, algorithms              | `BACKEND.md`                   |
| Agent behavior, hackathon constraints, contracts | This file                      |
| Next.js APIs                                     | `node_modules/next/dist/docs/` |

When `BACKEND.md` and this file conflict on **product behavior**, follow this file. When they conflict on **implementation detail**, follow `BACKEND.md`.
