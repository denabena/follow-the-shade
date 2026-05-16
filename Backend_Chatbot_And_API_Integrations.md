# Follow the Shade - Backend Handoff and API Research

This document is for the next AI/backend agent and the frontend helper. The goal is to turn the current chatbot codebase into **Follow the Shade**, a conversational Split cafe finder that understands natural-language requests like “I want a sunny cafe near Riva from 3 to 5 today” and returns map-ready cafe results with real sun/shade analysis.

## Product Summary

**Name:** Follow the Shade  
**City:** Split, Croatia  
**Core promise:** “Tell us where and when you want to sit outside in Split, and we will check which cafe terraces are actually sunny or shaded.”

The app should feel like a local friend checked the conditions, not like a generic places search. The user does not operate filters. They chat naturally. The backend extracts:

- preferred exposure: `sun`, `shade`, or `either`
- requested date and time window
- Split area, street, landmark, or “near me” location
- whether cafes must be open during the window
- whether the answer should optimize for sun/shade, distance, rating, busyness, or outdoor seating confidence

Important Split framing:

- Default unresolved city to **Split**, not Croatia generally.
- If the user asks outside Split, clarify gently: “I’m focused on Split. Do you want something around Riva, Bačvice, Marmontova, Varoš, or another Split area?”
- The example “Tkalčićeva street” is Zagreb, not Split. Do not seed the Split demo around that street.
- Good demo areas: Riva, Diocletian’s Palace / Pjaca, Marmontova, Prokurative, Matejuška, Varoš, Bačvice, Firule, Žnjan, West Coast, Sustipan.

## Recommended 9-Hour MVP

Build the backend around one deterministic composite tool:

```text
find_split_cafe_sun_shade(query: str, thread_id: str, now_iso: str) -> JSON
```

The tool should do the whole pipeline:

1. Parse the user request into a strict schema.
2. Geocode the Split area or landmark.
3. Find cafe candidates with outdoor-seating evidence.
4. Fetch nearby building geometry and approximate heights.
5. Compute geometric sun/shade samples across the requested time window.
6. Optionally fetch cloud cover.
7. Persist the analysis payload under an `analysis_id`.
8. Return compact JSON for the LLM plus the same map payload for the frontend.

Why one composite tool? The current app already uses LangChain tools, but a 9-hour hackathon does not need the model orchestrating five fragile geospatial calls. Let the LLM decide when to call the tool and how to explain the result. Keep geometry, ranking, persistence, and source metadata deterministic.

Recommended MVP stack:

- **Agent/runtime:** Keep current FastAPI + LangChain/LangGraph structure.
- **Places:** Google Places API (New) if a key is available; OSM Overpass fallback.
- **Buildings:** OpenStreetMap via Overpass API.
- **Sun position:** Python `astral`.
- **Shadow geometry:** Python `shapely` + `pyproj`; optionally try `pybdshadow`, but do not block on it.
- **Weather nuance:** Open-Meteo hourly `cloud_cover`.
- **Voice:** Keep Soniox STT/TTS from the current app so users can ask naturally by voice and optionally hear the recommendation.
- **Frontend:** Reuse `agent.html` only as a light chat shell reference. Give the frontend helper API contracts and small chatbot-behavior hints, not a full UI rebuild plan.
- **Optional visual overlay:** `leaflet-shadow-simulator` can be mentioned as an optional frontend enhancement only, not as the source of truth for the agent answer.

## A. Existing Project Code to Reuse

Use these files as the base rather than starting fresh.

### Core Runtime

- `src/app/main.py`
  - FastAPI app setup, CORS, `/chat` UI route, static `/assets`.
  - Reuse route registration and static `agent.html` serving.

- `src/app/lifespan.py`
  - Startup/shutdown wiring.
  - Loads `agent_config.yaml`.
  - Builds `ModelFactory`, `ToolRegistry`, `AgentFactory`, `GraphFactory`.
  - Sets up LangGraph checkpointer/store with Redis fallback to memory.
  - Add `AnalysisStore` here and pass it into `ToolRegistry` dependencies.

- `src/app/state.py`
  - Holds app container state.
  - Add fields like `analysis_store`, `places_client`, or `shadow_service` if needed.

- `src/core/config.py`
  - Env-backed settings.
  - Add API keys and base URLs here:
    - `GOOGLE_MAPS_API_KEY`
    - `FOURSQUARE_API_KEY`
    - `OUTSCRAPER_API_KEY`
    - `SHADOWMAP_API_KEY`
    - `SHADEMAP_API_KEY`
    - `OVERPASS_URL`
    - `OPEN_METEO_BASE_URL`
    - `SONIOX_API_KEY`
    - `SONIOX_API_KEY_TTS`
    - `SONIOX_STT_MODEL`
    - `SONIOX_TTS_MODEL`
    - `SONIOX_TTS_VOICE`

### Agent Builders

- `src/app/builders/model_factory.py`
  - Provider factory for OpenAI/Anthropic/Mistral.
  - Fine for MVP. Use OpenAI unless the hackathon requires another provider.

- `src/app/builders/tool_registry.py`
  - Auto-discovers any `BaseTool` or `@tool` instance under `src/tools`.
  - Constructor dependency injection already exists. This is perfect for injecting `settings`, `tracer`, and the new `analysis_store`.
  - Supports async startup and shutdown hooks via `ainitialize` / `aclose`.

- `src/app/builders/agent_factory.py`
  - Resolves domain tools from YAML.
  - Supports Human-in-the-Loop middleware.
  - Supports structured response via `StructuredChatAnswer`.
  - Extend or replace the structured answer schema with a Follow the Shade schema if needed.

- `src/app/builders/graph_factory.py`
  - Multi-agent graph with handoff tools.
  - MVP can use a single `Agent_FollowTheShade`.
  - Keep handoff machinery if a later frontend/helper agent wants a separate “MapExplanationAgent” or “BookingAgent”.

- `src/app/graph_state.py`
  - Existing multi-agent state model. Use as-is unless adding explicit map state.

### Chat API and Response Extraction

- `src/app/api/chat/schemas.py`
  - Extend `ChatResponse` with:

```python
analysis_id: Optional[str] = None
map_payload: Optional[Dict[str, Any]] = None
```

- Keep `sources`, `audio`, `detected_language` if voice stays.

- `src/app/api/chat/routes.py`
  - Main endpoint is `POST /chat/final_answer`.
  - It already returns answer, thread, sources, HITL fields, optional audio.
  - Add map payload extraction after `run_chat_flow`.
  - Add `GET /chat/analysis/{analysis_id}` if frontend needs reload/recovery.
  - Keep the existing Soniox speech endpoints:
    - `POST /chat/speech/stt-key`
    - `POST /chat/speech/tts-key`
  - Keep `_generate_soniox_tts` for server-side generated answer audio when `include_audio=true`.

- `src/app/api/chat/generate_answer.py`
  - Currently extracts text, structured answer, and RAG sources from `ToolMessage`s.
  - Add a sibling to `extract_tool_sources`, for example:

```python
def extract_map_payload(response: dict | None) -> dict[str, Any] | None:
    for message in response.get("messages", []):
        if isinstance(message, ToolMessage) and message.name == "find_split_cafe_sun_shade":
            data = json.loads(_coerce_message_content(message.content))
            return data.get("map_payload") or data
    return None
```

- Then return it in `ChatFlowResult`.

### Existing Tool Patterns

- `src/tools/get_faq_info_tool.py`
  - Best pattern for the new composite tool:
    - Pydantic args schema
    - YAML description override
    - async `_arun`
    - injected dependencies
    - startup initialization hook

- `src/tools/get_passage_info_tool.py`
  - Simple JSON-returning tool pattern.
  - The new `find_split_cafe_sun_shade` tool should return JSON, not prose, so the frontend can use it.

- `src/tools/utils.py`
  - Reuse `get_tool_config` and `override_field_descriptions_from_schema`.

### Config and Prompt

- `agent_config.yaml`
  - Replace BINA content with Follow the Shade config.
  - Add one active tool: `find_split_cafe_sun_shade`.
  - Use the prompt draft below.

Draft prompt core:

```text
# ROLE
You are Follow the Shade, a local Split assistant that helps people find outdoor cafe seating in sun or shade.

# WORKFLOW
- If the user asks for a cafe in Split with sun/shade at a date/time, call find_split_cafe_sun_shade exactly once.
- If date or time is missing, ask one concise clarifying question.
- If location is missing, default to central Split/Riva unless the user’s wording implies “near me”.
- If the request is outside Split, ask them to choose a Split area.
- Do not invent sun/shade results. Use the tool output.
- Explain uncertainty: estimated terrace point, missing building heights, cloudy weather, or partial exposure.
- Return brief, natural advice and mention 2-4 best matches.

# FINAL OUTPUT
Return only JSON:
{
  "response": "natural answer",
  "detected_language": "hr/en/it/de/sl/fr"
}
```

### Soniox Speech Reuse

The current root app already has a solid Soniox integration in `src/app/api/chat/routes.py`. Keep it and rebrand the prompt/context terms for Split cafes.

- `POST /chat/speech/stt-key`
  - Creates a short-lived Soniox key for browser microphone transcription.
  - Current helper: `_create_soniox_temporary_key(usage_type="transcribe_websocket")`.
  - Current STT config builder: `_build_soniox_stt_config()`.
  - Update context terms from BINA toll words to Split/cafe/sun words, for example:
    - `Follow the Shade`
    - `Split`
    - `Riva`
    - `Bacvice`
    - `Marmontova`
    - `Diocletian Palace`
    - `shade`
    - `sunny terrace`
    - `outdoor seating`

- `POST /chat/speech/tts-key`
  - Creates a short-lived Soniox key for realtime browser TTS playback.
  - Current helper: `_create_soniox_temporary_key(usage_type="tts_rt")`.
  - Current TTS config builder: `_build_soniox_tts_config(language)`.

- `include_audio=true` on `/chat/final_answer`
  - Current backend can generate a complete answer audio blob through `_generate_soniox_tts`.
  - This is good enough for MVP if realtime TTS is too much for the frontend.

Recommended hackathon approach:

1. Keep both temporary-key endpoints exactly as API surfaces.
2. Update Soniox STT context terms and default language hints to `hr,en,it,de,sl,fr`.
3. Keep TTS optional. Text response + map is the primary UX; voice is a polished layer.
4. Do not expose the main Soniox API key to the browser. The browser should only receive temporary keys.

Current Soniox docs to know:

- Real-time STT uses a WebSocket endpoint and can authenticate with a main or temporary API key.
- Soniox recommends temporary API keys for client apps.
- REST TTS endpoint is `POST https://tts-rt.soniox.com/tts`.
- Realtime TTS WebSocket endpoint is `wss://tts-rt.soniox.com/tts-websocket`.

Sources:

- Soniox STT WebSocket API: https://soniox.com/docs/stt/api-reference/websocket-api
- Soniox API reference: https://soniox.com/docs/stt/api-reference
- Soniox TTS REST generation: https://soniox.com/docs/tts/rest-api/generate-speech
- Soniox realtime TTS: https://soniox.com/docs/tts/rt/real-time-generation

### Frontend Reuse Notes

- `agent.html`
  - Treat this as a reference for how the chatbot talks to the backend, not as a design spec.
  - Useful hints to reuse: `POST /chat/final_answer`, `thread_id`, `include_audio`, pending HITL shape, `sources`, and Soniox speech-key calls.
  - The frontend helper should build the actual Follow the Shade experience around the new `answer`, `analysis_id`, and `map_payload` contract.
  - Avoid sliders/filters in the product. The chat asks clarifying questions; the map displays results.

- `Abysalto-AbysaltoPeople/widget/embed.js`
  - Use only as a light reference for embeddable chat mechanics.
  - Do not spend backend-agent time porting this widget unless the team explicitly chooses an embedded distribution.

### Submodule Patterns Worth Reusing

- `Abysalto-AbysaltoPeople/packages/abysalto-people-ai/src/abysalto_people_ai/agent/tools/base.py`
  - Contains `ConfiguredTool`, a cleaner YAML-configured `BaseTool` wrapper.
  - Consider copying this pattern into root `src/tools/base.py`.

- `Abysalto-AbysaltoPeople/packages/abysalto-people-ai/src/abysalto_people_ai/services/runtime_store.py`
  - Simple process-local store pattern.
  - Adapt into `src/app/analysis_store.py`:
    - `save_analysis(record)`
    - `get_analysis(analysis_id)`
    - TTL cleanup
    - Redis implementation if time allows

- `Abysalto-AbysaltoPeople/packages/abysalto-people-ai/src/abysalto_people_ai/agent/middleware/datetime_system_prompt.py`
  - Useful for relative dates like “today”, “tomorrow”, “Saturday afternoon”.
  - Copy/adapt to root so the model always sees current `Europe/Zagreb` date/time.

- `Abysalto-AbysaltoPeople/packages/abysalto-people-ai/src/abysalto_people_ai/api/chat/routes.py`
  - Shows a bearer-token pattern and alternate chat endpoints.
  - Not necessary for MVP, but useful if API auth is added.

### Tests

- `tests/test_chat_routes.py`
  - Pattern for fake agent app route tests.
  - Add tests that a tool message containing map payload appears in `ChatResponse`.

- `tests/test_tool_utils.py`
  - Keep YAML schema override tests.

- Add focused tests:
  - request parsing for “today”, “this Saturday afternoon”
  - OSM height parsing: `height`, `building:levels`, default fallback
  - shadow score with synthetic rectangle building and terrace point
  - Google Places response normalization
  - `map_payload` extraction from tool message

## B. API and Library Options

### 1. OpenAI / LangChain Tool Calling

Current project already uses LangChain `create_agent` and tool objects. Keep this abstraction.

Relevant current OpenAI guidance:

- Function/tool calling is a multi-step flow: model receives tool definitions, emits tool calls, application executes code, sends tool outputs, then the model produces final answer.
- Strict function schemas are recommended for reliable tool arguments.
- Structured outputs are appropriate for final assistant responses when the app needs typed fields.

Sources:

- OpenAI function calling docs: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI structured outputs docs: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI tools docs: https://developers.openai.com/api/docs/guides/tools

MVP use:

- Let LangChain handle tool calling.
- Use one composite backend tool with a Pydantic args schema.
- Keep final response structured with `response` and `detected_language`.
- Do not make the model calculate geometry. The model should explain deterministic tool output.

### 2. Soniox Speech API

Use Soniox for voice input and optional voice output. The current app already contains the required backend shape, so this should be a reuse task rather than a fresh integration.

What to keep:

- Server creates temporary API keys.
- Browser uses temporary keys for realtime STT/TTS.
- Backend can generate non-realtime TTS audio when `include_audio=true`.
- Main Soniox keys remain in `.env` and never go to the frontend.

What to change:

- Replace BINA-specific STT context terms with Follow the Shade terms.
- Set the speech UX copy to match Split cafes, sun, shade, and outdoor seating.
- Keep multilingual hints because tourists in Split may ask in Croatian, English, Italian, German, Slovenian, or French.

Sources:

- Soniox STT WebSocket API: https://soniox.com/docs/stt/api-reference/websocket-api
- Soniox API reference: https://soniox.com/docs/stt/api-reference
- Soniox TTS REST generation: https://soniox.com/docs/tts/rest-api/generate-speech
- Soniox realtime TTS: https://soniox.com/docs/tts/rt/real-time-generation

### 3. Google Places API (Recommended Place Source)

Use for cafe search, official place metadata, opening hours, ratings, address, map links, and outdoor seating when available.

Endpoints:

- Text Search (New): `POST https://places.googleapis.com/v1/places:searchText`
- Nearby Search (New): `POST https://places.googleapis.com/v1/places:searchNearby`
- Place Details (New): `GET https://places.googleapis.com/v1/places/{place_id}`

Important connection notes:

- Send API key in `X-Goog-Api-Key`.
- Send exact fields in `X-Goog-FieldMask`; Google returns an error if omitted and wildcard `*` is discouraged in production.
- Useful fields:
  - `places.id`
  - `places.name`
  - `places.displayName`
  - `places.formattedAddress`
  - `places.location`
  - `places.types`
  - `places.rating`
  - `places.userRatingCount`
  - `places.regularOpeningHours`
  - `places.currentOpeningHours`
  - `places.outdoorSeating`
  - `places.servesCoffee`
  - `places.priceLevel`
  - `places.googleMapsUri`
  - `places.photos`
- For Nearby Search, Google supports `includedTypes: ["restaurant", "cafe"]`, `locationRestriction.circle`, and `rankPreference`.
- `outdoorSeating` and `servesCoffee` are higher-cost Atmosphere fields. If the hackathon budget is tight, use them only in Place Details for top candidates.

Example cafe search:

```python
async def google_nearby_cafes(client, api_key, lat, lng, radius_m=900):
    payload = {
        "includedTypes": ["cafe"],
        "maxResultCount": 20,
        "rankPreference": "POPULARITY",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_m,
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.location,places.rating,places.userRatingCount,"
            "places.regularOpeningHours,places.googleMapsUri,places.outdoorSeating"
        ),
    }
    r = await client.post(
        "https://places.googleapis.com/v1/places:searchNearby",
        json=payload,
        headers=headers,
    )
    r.raise_for_status()
    return r.json().get("places", [])
```

Sources:

- Google Text Search docs: https://developers.google.com/maps/documentation/places/web-service/text-search
- Google Nearby Search docs: https://developers.google.com/maps/documentation/places/web-service/nearby-search
- Google Place Details docs: https://developers.google.com/maps/documentation/places/web-service/place-details

Watchouts:

- Google does not provide official “popular times” through Places API.
- Opening hours can be incomplete or exception-heavy. Be honest if future holiday hours are unknown.
- Google Maps Platform has billing and EEA-specific terms; check hackathon key terms before production.
- If using Google place data on a map, follow Google attribution/display rules. If using Leaflet with OSM tiles, be careful mixing Google POI data with non-Google maps for anything beyond hackathon/demo use.

### 4. OpenStreetMap Overpass API (Recommended Building Source + Fallback Cafes)

Use Overpass for:

- building footprints around candidate cafes
- `height`, `building:levels`, `roof:height`, `building:part`
- fallback cafe POIs
- possible outdoor seating tags/polygons

Overpass is a read-only API for querying selected OSM map data. It is free but shared infrastructure, so cache aggressively and avoid high-frequency polling.

Building query around a bounding box:

```overpass
[out:json][timeout:25];
(
  way["building"](south,west,north,east);
  relation["building"](south,west,north,east);
  way["building:part"](south,west,north,east);
  relation["building:part"](south,west,north,east);
);
out body;
>;
out skel qt;
```

Cafe fallback query:

```overpass
[out:json][timeout:25];
(
  node["amenity"="cafe"](south,west,north,east);
  way["amenity"="cafe"](south,west,north,east);
  relation["amenity"="cafe"](south,west,north,east);
  way["leisure"="outdoor_seating"](south,west,north,east);
  relation["leisure"="outdoor_seating"](south,west,north,east);
);
out body center;
>;
out skel qt;
```

Height fallback:

```python
def estimate_height_m(tags: dict) -> tuple[float, str]:
    if tags.get("height"):
        return parse_meters(tags["height"]), "height"
    if tags.get("building:height"):
        return parse_meters(tags["building:height"]), "building:height"
    if tags.get("building:levels"):
        return float(tags["building:levels"]) * 3.0, "building:levels*3m"
    if tags.get("levels"):
        return float(tags["levels"]) * 3.0, "levels*3m"
    return 9.0, "default_9m"
```

Sources:

- Overpass API overview: https://wiki.openstreetmap.org/wiki/Overpass_API
- `building:levels` guidance: https://wiki.openstreetmap.org/wiki/Key:building:levels
- OSM `amenity=cafe`: https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dcafe
- OSM `outdoor_seating`: https://wiki.openstreetmap.org/wiki/Key:outdoor_seating

Watchouts:

- Split old town has dense building geometry, but heights may be sparse.
- `building:levels` uses floors, not meters; OSM suggests 3m/floor as a common default when no height tag exists.
- Terraces are often not mapped as polygons. Build confidence levels.
- Cache by bbox and TTL; Overpass can throttle/time out.

### 5. Nominatim / OSM Geocoding (Fallback Only)

Use only if Google geocoding is unavailable.

Nominatim public service is not for client-side autocomplete, bulk/systematic queries, or scraping details pages. Use server-side, with caching, a clear User-Agent, and low rate.

Source:

- Nominatim usage policy: https://operations.osmfoundation.org/policies/nominatim/

MVP:

- Prefer Google Places Text Search for “Riva Split”, “Bačvice”, “Marmontova Split”.
- Use a hardcoded Split landmark dictionary for demo reliability.

Seed dictionary:

```python
SPLIT_LANDMARKS = {
    "riva": (43.5081, 16.4391),
    "marmontova": (43.5100, 16.4385),
    "pjaca": (43.5088, 16.4398),
    "bacvice": (43.5027, 16.4485),
    "matejuska": (43.5088, 16.4349),
    "varos": (43.5108, 16.4335),
    "znjan": (43.5040, 16.4785),
}
```

### 6. ShadeMap App / Leaflet Shadow Simulator

The user-provided `shademap.app` URL is an interactive app state URL, not a normal backend REST API.

There are two different things:

1. **ShadeMap JS toolkit / `leaflet-shadow-simulator`**
   - Browser toolkit.
   - Can visualize shadows and check if a pixel is in sun/shade after the layer renders.
   - Requires an API key from ShadeMap.
   - Supports custom terrain tiles and custom GeoJSON building features.

2. **Shadowmap API**
   - Separate commercial/early-access API.
   - Advertises a point sunlight endpoint that returns whether a coordinate is in direct sunlight at a given time, considering 3D obstacles.
   - Currently onboarding select partners, so do not rely on access during a 9-hour hackathon.

Sources:

- ShadeMap about/docs: https://shademap.app/about/
- Leaflet shadow simulator GitHub: https://github.com/ted-piotrowski/leaflet-shadow-simulator
- Shadowmap API: https://shadowmap.org/api

MVP recommendation:

- Do **not** make ShadeMap the backend source of truth unless an API key and stable integration are already available.
- Mention `leaflet-shadow-simulator` only as an optional frontend visual overlay.
- Backend should return its own deterministic sun/shade result.

For point checks, the library exposes `isPositionInSun(x, y)` and `isPositionInShade(x, y)` after the shadow layer has rendered. That is useful for frontend validation but awkward for backend persistence unless running a headless browser.

### 7. Python Shadow Geometry

Recommended MVP backend implementation:

- `astral` for sun azimuth/elevation.
- `pyproj` to project WGS84 into meters.
- `shapely` for building polygons, shadow polygons, and point-in-polygon tests.

Split is in UTM zone 33N, so `EPSG:32633` is a practical metric CRS. Croatia’s local CRS can be more precise, but UTM is enough for a hackathon cafe terrace shadow analysis.

Basic algorithm:

```python
from math import radians, tan, sin, cos
from shapely import affinity
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from astral import Observer
from astral.sun import azimuth, elevation

def shadow_for_building(poly_m: Polygon, height_m: float, sun_azimuth_deg: float, sun_elevation_deg: float):
    if sun_elevation_deg <= 0:
        return None

    length = height_m / tan(radians(sun_elevation_deg))
    shadow_azimuth = radians((sun_azimuth_deg + 180.0) % 360.0)
    dx = length * sin(shadow_azimuth)
    dy = length * cos(shadow_azimuth)

    shifted = affinity.translate(poly_m, xoff=dx, yoff=dy)
    coords = list(poly_m.exterior.coords)
    strips = []
    for p1, p2 in zip(coords, coords[1:]):
        strips.append(Polygon([p1, p2, (p2[0] + dx, p2[1] + dy), (p1[0] + dx, p1[1] + dy)]))
    return unary_union(strips + [shifted]).difference(poly_m)
```

For each candidate terrace point:

1. Sample times every 15 or 20 minutes across the requested window.
2. Compute sun position at cafe coordinates.
3. Build union of nearby shadow polygons.
4. `is_sunny = not shadow_union.contains(point_m)` when sun elevation > 0.
5. Compute `sun_ratio = sunny_samples / total_samples`.
6. For shade preference, match score is `1 - sun_ratio`.
7. Detect transitions, e.g. “sunny until 16:30, shaded after.”

Source:

- Astral sun position docs: https://astral.readthedocs.io/en/latest/package.html

Optional library:

- `pybdshadow` can calculate building shadows from a building GeoDataFrame and datetime, using a height column.
- It may pull in heavier geospatial dependencies and may be risky with Python 3.13 during a short hackathon.
- Try it only if install is smooth.

Source:

- pybdshadow docs: https://pybdshadow.readthedocs.io/en/latest/bdshadow.html

### 8. Google Solar API (Interesting, Not MVP)

Google Solar API can return raw solar data layers such as DSM, imagery, building masks, flux, and hourly shade GeoTIFFs.

Potential use:

- High-quality DSM/shade data where covered.
- Could replace OSM-height approximation in production.

Why not MVP:

- It is aimed at solar/rooftop workflows, not terrace point checks.
- GeoTIFF handling adds complexity.
- Coverage may return 404 in some areas despite approximate coverage maps.
- EEA terms/content restrictions need review.

Sources:

- Solar API overview: https://developers.google.com/maps/documentation/solar/overview
- Solar data layers docs: https://developers.google.com/maps/documentation/solar/reference/rest/v1/dataLayers
- Solar coverage docs: https://developers.google.com/maps/documentation/solar/coverage

### 9. Open-Meteo Weather API

Use for weather nuance, especially cloud cover. The geometry answers “would this point be in direct sun if the sky is clear?” but users care if it is cloudy.

Endpoint:

```text
GET https://api.open-meteo.com/v1/forecast
```

Example:

```text
https://api.open-meteo.com/v1/forecast?latitude=43.5081&longitude=16.4391&hourly=cloud_cover,temperature_2m,precipitation_probability&timezone=Europe%2FZagreb&start_date=2026-05-16&end_date=2026-05-16
```

Use fields:

- `cloud_cover`
- `temperature_2m`
- `precipitation_probability`
- optionally `wind_speed_10m`

Source:

- Open-Meteo docs: https://open-meteo.com/en/docs

UX rule:

- If user asks for sun and geometric sun is good but cloud cover is high, say: “Geometrically it should be sunny, but the forecast is cloudy, so it may not feel like direct sun.”
- If user asks for shade and cloud cover is high, results are still useful for glare/heat, but phrase less dramatically.

### 10. Foursquare Places API

Useful alternative to Google Places, especially if you want popularity/rating metadata. It supports `GET https://api.foursquare.com/v3/places/search`, fields selection, `ll`, `radius`, `query`, `open_now`, `open_at`, and sorting by relevance/rating/distance/popularity.

Pros:

- Good POI coverage.
- `popularity` field is a foot-traffic-style score.
- Search endpoint supports sort options.

Cons:

- Outdoor seating is not as direct/reliable as Google `outdoorSeating`.
- Requires account/key.
- Still not exact live terrace occupancy.

Sources:

- Place Search docs: https://docs.foursquare.com/developer/reference/place-search
- Response fields docs: https://docs.foursquare.com/developer/reference/response-fields

MVP role:

- Backup place source if Google key is missing.
- Optional tie-breaker for “not too busy” if Google popular times is unavailable.

### 11. Popular Times / Busyness

This is optional. It is not core to sun/shade.

Options:

- `populartimes` Python library
  - Unofficial scraper around Google data.
  - Can break when Google changes pages.
  - Possible ToS/legal risk.

- Outscraper
  - Commercial API/scraper that exposes Google Maps data including popular times.
  - More stable than DIY scraping.
  - Requires key and budget.

Sources:

- Populartimes GitHub: https://github.com/m-wrzr/populartimes
- Outscraper docs: https://docs.outscraper.com/
- Outscraper popular times article: https://outscraper.com/places-api-popular-times/

MVP recommendation:

- Do not implement busyness unless everything else is done.
- If included, make it a ranking nuance, not a promise: “usually quieter around 15:00.”

## C. Things to Look Out For

### Terrace Position Is the Hardest Product Detail

Google and OSM usually give the cafe business point, not the exact outdoor terrace polygon. That point may be inside the building, which would make every terrace look shaded by the cafe’s own building.

Recommended confidence tiers:

- `high`: matched OSM `leisure=outdoor_seating` polygon or manually seeded terrace point.
- `medium`: outdoor seating is confirmed by Google/OSM, terrace point estimated outside building.
- `low`: cafe has unknown outdoor seating; sampled around POI.

MVP strategy:

1. Search OSM for `leisure=outdoor_seating` within 35m of cafe name/location.
2. If found, use polygon centroid and maybe 2-3 interior sample points.
3. Else, if Google says `outdoorSeating=true`, generate 6-8 sample points in a 6-15m ring around the cafe and use the best/majority point.
4. Else, keep the cafe but mark `outdoor_seating_confidence="unknown"` and rank lower.
5. For demo reliability, add a small `assets/split_cafe_seed.json` with known Split terrace coordinates for the cafes you plan to showcase.

### Building Heights Are Often Missing

Shadow accuracy depends heavily on building heights. Many OSM buildings have footprints but no height. Use:

1. `height`
2. `building:height`
3. `building:levels * 3`
4. `levels * 3`
5. local default, e.g. 9m or 12m in old town

Return confidence:

- `height_confidence="exact_tag"` for `height`
- `height_confidence="levels_estimate"` for `building:levels`
- `height_confidence="default_estimate"` for defaults

The answer should mention uncertainty only when it changes the recommendation.

### Coordinate Math Can Quietly Break

Do not compute shadows directly in lat/lng degrees. Project to a metric CRS first.

For Split:

- WGS84 input/output: `EPSG:4326`
- Metric working CRS: `EPSG:32633`

Test with one synthetic building and point before using real OSM geometry.

### The Sun/Shade Definition Must Be Clear

Backend result should distinguish:

- `geometric_direct_sun`: no building shadow covers point and sun is above horizon
- `weather_adjusted_feel`: cloud cover/precipitation may make sun irrelevant
- `shade_source`: building shadow only; not umbrellas, trees, awnings, sails, or cafe parasols unless data is added

Phrase examples:

- “The terrace should be in direct sun for most of your window.”
- “This is building-shadow analysis; cafe umbrellas may add shade even when the map says sunny.”
- “Forecast cloud cover is high, so direct-sun picks may not feel very sunny today.”

### Time Parsing Needs Runtime Date

The current date in the running environment should be injected into the prompt/tool. Use `Europe/Zagreb`.

Natural language defaults:

- “today”: current Zagreb date.
- “tomorrow”: next Zagreb date.
- “this Saturday”: upcoming Saturday. If today is Saturday and time is still future, use today; otherwise next Saturday.
- “afternoon”: default `14:00-18:00`.
- “morning”: `09:00-12:00`.
- “lunch”: `12:00-14:00`.
- “sunset”: use Astral sunset, with a window like `sunset-90m` to `sunset`.
- No time: ask a short clarification.

### Keep the Frontend Conversational

Keep this as a product/API note, not a UI spec. The user should not see filters; they should ask naturally, receive clarifying questions in chat when needed, and see `map_payload` rendered by the frontend helper. The backend handoff should avoid prescribing marker colors, layout, or component structure beyond the required data fields.

### Persist Results Explicitly

LangGraph checkpointer persists conversation state, but the frontend needs typed analysis data. Do not make the frontend scrape prose.

Recommended additions:

```python
@dataclass
class AnalysisRecord:
    analysis_id: str
    thread_id: str
    created_at: str
    expires_at: str
    query: str
    parsed_request: dict
    map_payload: dict
```

Implement:

- `src/app/analysis_store.py`
  - `InMemoryAnalysisStore` for local demo
  - optional `RedisAnalysisStore` for Docker
- Add `analysis_store` to `AppState`.
- Tool saves record and returns `analysis_id`.
- `ChatResponse` includes `analysis_id` and `map_payload`.
- `GET /chat/analysis/{analysis_id}` returns the same payload.

### API Key Handling

Do not expose backend keys in `agent.html`.

Safe:

- Google Places key on backend only.
- Outscraper key on backend only.
- Shadowmap API key on backend only.

Maybe frontend:

- Leaflet tile keys if public/restricted.
- ShadeMap browser API key only if domain-restricted and terms allow it.

Current `.env` is open in the IDE. Do not paste secrets into docs/tests.

### Licensing and Attribution

For hackathon demo, keep attribution visible:

- OSM/Leaflet map: OpenStreetMap attribution.
- Overpass/OSM data: OpenStreetMap contributors.
- Google Places data: follow Google Maps Platform display requirements.
- Foursquare data: follow Foursquare attribution/terms.
- ShadeMap/Shadowmap: follow their API key and commercial rules.

### Performance

Potential bottlenecks:

- Overpass query latency.
- Too many building polygons.
- Shapely union of all shadows at many timestamps.
- Google Place Details per candidate.

MVP constraints:

- Cap candidates at 12.
- Cap buildings to radius 350-500m around candidate cluster.
- Sample every 20 or 30 minutes, not every minute.
- Cache Overpass results by rounded bbox.
- Cache place search by area/radius for a few minutes.
- Only fetch Place Details for top 10-12 candidates.

### Failure Modes

Handle explicitly:

- No cafes found: broaden radius once, then ask user for another Split area.
- No building data: return places but mark shadow confidence low.
- Sun below horizon: all are shaded; recommend open/pleasant places, not “sun”.
- Bad time range: ask for a valid time.
- External API down: use fallback source or return honest partial result.
- User asks for “near me” but no coordinates: ask them to share area or enable location if frontend supports it.

## Suggested Data Contracts

### Parsed Request

```json
{
  "preference": "shade",
  "location_text": "Riva",
  "center": { "lat": 43.5081, "lng": 16.4391 },
  "radius_m": 900,
  "start": "2026-05-16T15:00:00+02:00",
  "end": "2026-05-16T17:00:00+02:00",
  "must_be_open": true,
  "language": "en"
}
```

### Map Payload

```json
{
  "analysis_id": "shade_20260516_abc123",
  "generated_at": "2026-05-16T12:15:00+02:00",
  "request": {
    "preference": "shade",
    "location_label": "Riva, Split",
    "start": "2026-05-16T15:00:00+02:00",
    "end": "2026-05-16T17:00:00+02:00"
  },
  "map": {
    "center": { "lat": 43.5081, "lng": 16.4391 },
    "zoom": 16
  },
  "results": [
    {
      "id": "google:ChIJ...",
      "name": "Cafe Example",
      "provider": "google_places",
      "location": { "lat": 43.5084, "lng": 16.4394 },
      "terrace_point": { "lat": 43.50835, "lng": 16.43955 },
      "address": "Obala Hrvatskog narodnog preporoda, Split",
      "google_maps_uri": "https://maps.google.com/...",
      "rating": 4.5,
      "user_rating_count": 430,
      "is_open_for_window": true,
      "outdoor_seating": {
        "value": true,
        "source": "google_places",
        "confidence": "medium"
      },
      "exposure": {
        "preference": "shade",
        "match_score": 0.84,
        "label": "strong_match",
        "summary": "Mostly shaded from 15:00 to 17:00.",
        "sun_ratio": 0.16,
        "samples": [
          { "time": "2026-05-16T15:00:00+02:00", "state": "shade" },
          { "time": "2026-05-16T15:30:00+02:00", "state": "shade" },
          { "time": "2026-05-16T16:00:00+02:00", "state": "sun" },
          { "time": "2026-05-16T16:30:00+02:00", "state": "shade" },
          { "time": "2026-05-16T17:00:00+02:00", "state": "shade" }
        ],
        "transition_notes": ["brief sun patch around 16:00"],
        "confidence": "medium",
        "confidence_reasons": [
          "building heights partly estimated",
          "terrace point estimated"
        ]
      },
      "weather": {
        "cloud_cover_avg": 18,
        "precipitation_probability_max": 5
      }
    }
  ],
  "source_notes": [
    "Cafe data from Google Places.",
    "Building geometry from OpenStreetMap/Overpass.",
    "Building heights estimated where OSM height tags were missing.",
    "Weather from Open-Meteo."
  ]
}
```

## Suggested File Additions

Backend:

```text
src/app/analysis_store.py
src/services/places/google_places.py
src/services/places/osm_places.py
src/services/geocoding/split_geocoder.py
src/services/geodata/overpass_client.py
src/services/shadow/sun_position.py
src/services/shadow/shadow_engine.py
src/services/weather/open_meteo.py
src/tools/find_split_cafe_sun_shade_tool.py
assets/split_cafe_seed.json
```

Tests:

```text
tests/test_split_geocoder.py
tests/test_google_places_normalization.py
tests/test_overpass_building_parser.py
tests/test_shadow_engine.py
tests/test_analysis_payload_extraction.py
```

Frontend:

```text
agent.html
```

Only reference this file as the existing chat/API-call example. The frontend helper owns the actual Follow the Shade UI.

## Implementation Sketch

### Tool Input

```python
class FindSplitCafeSunShadeInput(BaseModel):
    query: str = Field(..., description="The user's natural language cafe sun/shade request.")
    thread_id: str = Field(..., description="Conversation thread id for persisting analysis.")
```

### Tool Output Shape

Return a JSON string:

```json
{
  "analysis_id": "...",
  "answer_facts": {
    "best_matches": ["Cafe A", "Cafe B"],
    "preference": "shade",
    "time_window_label": "today 15:00-17:00",
    "important_nuance": "Cafe B turns sunny around 16:30"
  },
  "map_payload": { "...": "..." }
}
```

### Tool Class

```python
class FindSplitCafeSunShadeTool(BaseTool):
    name: str = "find_split_cafe_sun_shade"
    description: str = "Find Split cafes and analyze whether their outdoor seating is in sun or shade for the requested time."
    args_schema: Any = FindSplitCafeSunShadeInput

    def __init__(self, settings, analysis_store, tracer=None, **kwargs):
        super().__init__(**kwargs)
        self.settings = settings
        self.analysis_store = analysis_store
        self.http = httpx.AsyncClient(timeout=20.0)

    async def aclose(self):
        await self.http.aclose()

    async def _arun(self, query: str, thread_id: str) -> str:
        parsed = await parse_request(query)
        cafes = await find_cafes(parsed)
        buildings = await fetch_buildings(cafes, parsed)
        weather = await fetch_weather(parsed)
        payload = analyze_and_rank(parsed, cafes, buildings, weather)
        analysis_id = await self.analysis_store.save(thread_id, query, payload)
        return json.dumps({"analysis_id": analysis_id, "map_payload": payload}, ensure_ascii=False)
```

Note: `parse_request` can be model-driven structured output or deterministic plus LLM. For speed, using the same OpenAI/LangChain model with a strict Pydantic schema is fine.

### Frontend Contract Hint

Keep frontend instructions intentionally light. The backend agent should only tell the frontend helper:

- Send user text to `POST /chat/final_answer` with a stable `thread_id`.
- Optionally set `include_audio=true` for backend-generated Soniox audio.
- Use `POST /chat/speech/stt-key` and `POST /chat/speech/tts-key` if the browser implements realtime Soniox voice.
- Render assistant prose from `answer`.
- Render map state from `map_payload`; do not parse the assistant prose for cafe data.
- Keep the UI conversational. Clarifying questions happen in chat, not through filter controls.

## Demo Script

Use queries that avoid ambiguity and show transitions:

1. “Find me a shady cafe outside near Riva today from 3 to 5pm.”
2. “I want sun around Bačvice tomorrow morning.”
3. “Somewhere near Marmontova that is shaded this Saturday afternoon.”
4. “I want a sunny terrace but not too crowded near the old town.”

Prepare seed data for 8-12 known Split cafes around Riva/Bačvice/Marmontova if API keys or terrace detection are unreliable.

## Priority Order for the Hackathon

1. Rename/rebrand config and prompt to Follow the Shade.
2. Rebrand Soniox STT context terms and keep the existing STT/TTS endpoints working.
3. Add `map_payload` and `analysis_id` to chat response.
4. Implement `AnalysisStore`.
5. Implement Google Places search or OSM fallback.
6. Implement Overpass building fetch and height parser.
7. Implement basic shadow engine with Astral/Shapely.
8. Give the frontend helper only the response contract and light chatbot hints.
9. Add Open-Meteo cloud cover.
10. Add terrace confidence and seed cafe overrides.
11. Optional: busyness via Foursquare/Outscraper.
12. Optional: frontend shadow overlay with `leaflet-shadow-simulator`.

## Source List

- OpenAI function calling: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI tools: https://developers.openai.com/api/docs/guides/tools
- Soniox STT WebSocket API: https://soniox.com/docs/stt/api-reference/websocket-api
- Soniox API reference: https://soniox.com/docs/stt/api-reference
- Soniox TTS REST generation: https://soniox.com/docs/tts/rest-api/generate-speech
- Soniox realtime TTS: https://soniox.com/docs/tts/rt/real-time-generation
- Google Places Text Search: https://developers.google.com/maps/documentation/places/web-service/text-search
- Google Places Nearby Search: https://developers.google.com/maps/documentation/places/web-service/nearby-search
- Google Places Details: https://developers.google.com/maps/documentation/places/web-service/place-details
- Google Solar API overview: https://developers.google.com/maps/documentation/solar/overview
- Google Solar data layers: https://developers.google.com/maps/documentation/solar/reference/rest/v1/dataLayers
- Google Solar coverage: https://developers.google.com/maps/documentation/solar/coverage
- OpenStreetMap Overpass API: https://wiki.openstreetmap.org/wiki/Overpass_API
- OSM `building:levels`: https://wiki.openstreetmap.org/wiki/Key:building:levels
- OSM `amenity=cafe`: https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dcafe
- OSM `outdoor_seating`: https://wiki.openstreetmap.org/wiki/Key:outdoor_seating
- Nominatim usage policy: https://operations.osmfoundation.org/policies/nominatim/
- ShadeMap about/docs: https://shademap.app/about/
- Leaflet shadow simulator: https://github.com/ted-piotrowski/leaflet-shadow-simulator
- Shadowmap API: https://shadowmap.org/api
- Astral docs: https://astral.readthedocs.io/en/latest/package.html
- pybdshadow docs: https://pybdshadow.readthedocs.io/en/latest/bdshadow.html
- Open-Meteo docs: https://open-meteo.com/en/docs
- Foursquare Place Search: https://docs.foursquare.com/developer/reference/place-search
- Foursquare response fields: https://docs.foursquare.com/developer/reference/response-fields
- Populartimes GitHub: https://github.com/m-wrzr/populartimes
- Outscraper docs: https://docs.outscraper.com/
