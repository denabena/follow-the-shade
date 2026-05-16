"use client"

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react"
import type {
  GeoJSONSource,
  LightsSpecification,
  Map as MapboxMap,
  Marker,
  Popup,
  PopupOptions,
} from "mapbox-gl"
import type { Cafe, CafeResult, IntentArea } from "@/lib/types"
import type { ShadeMapHandle } from "@/lib/shademap"
import { createShadeMap } from "@/lib/shademap"
import { cn } from "@/lib/cn"
import { SunGlyph } from "@/components/SunGlyph"

export type MapPanelHandle = {
  flyTo: (area: IntentArea) => Promise<void>
  awaitMapIdle: () => Promise<void>
  setShadeDate: (d: Date) => Promise<void>
  setShadeOpacity: (opacity: number) => void
  sampleSun: (lng: number, lat: number) => Promise<boolean>
  setResults: (results: CafeResult[], preference: "sun" | "shade" | "either") => void
  clearResults: () => void
  focusCafe: (cafe: Cafe) => void | Promise<void>
  resize: () => void
}

type MapStatus =
  | "loading"
  | "no-token"
  | "no-shademap-key"
  | "ready"
  | "error"
  | "invalid-token"

type Props = {
  onReady?: () => void
  onCafeClick?: (cafe: Cafe) => void
}

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? ""
const SHADEMAP_KEY = process.env.NEXT_PUBLIC_SHADEMAP_API_KEY ?? ""

const SPLIT_CENTER: [number, number] = [16.4402, 43.5081]

const CAFE_POPUP_OPTIONS = {
  offset: 12,
  closeButton: false,
  closeOnClick: true,
  maxWidth: "min(220px, 88vw)",
  className: "fts-cafe-popup",
  focusAfterOpen: false,
} satisfies PopupOptions

/** One fresh fix — helps when watchPosition has not fired yet. */
function requestFreshUserLngLat(): Promise<[number, number] | null> {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return Promise.resolve(null)
  }
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve([pos.coords.longitude, pos.coords.latitude]),
      () => resolve(null),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 15_000 },
    )
  })
}

/** GeoJSON source id; line + soft halo layers (ids must differ). */
const CAFE_ROUTE_SOURCE_ID = "cafe-route"
const CAFE_ROUTE_HALO_LAYER_ID = "cafe-route-halo"
const CAFE_ROUTE_LAYER_ID = "cafe-route-line"

const standardLights: LightsSpecification[] = [
  {
    id: "ambient_light",
    type: "ambient",
    properties: {
      color: "rgba(255, 246, 226, 1)",
      intensity: 0.36
    }
  },
  {
    id: "sun_light",
    type: "directional",
    properties: {
      color: "rgba(255, 255, 255, 1)",
      intensity: 0.58,
      direction: [180, 80],
      "cast-shadows": true,
      "shadow-intensity": 0.9,
      "shadow-quality": 1
    }
  }
]

const makeMarkerEl = (
  cafe: Cafe,
  _matched: boolean,
  _preference: "sun" | "shade" | "either",
  onClick: (e: MouseEvent) => void,
): HTMLElement => {
  const wrapper = document.createElement("button")
  wrapper.type = "button"
  wrapper.setAttribute("aria-label", `${cafe.name}, ${cafe.neighborhood}`)
  wrapper.className = cn(
    "group relative -translate-x-1/2 -translate-y-1/2 cursor-pointer",
    "outline-none focus-visible:ring-2 focus-visible:ring-terracotta",
  )
  wrapper.innerHTML = `
    <span class="relative flex h-2.5 w-2.5 items-center justify-center transition-transform duration-300 group-hover:scale-125">
      <span class="fts-marker-dot-pulse block size-[7px] min-h-[7px] min-w-[7px] rounded-full border border-terracotta-deep bg-terracotta"></span>
    </span>
    <span class="pointer-events-none absolute left-1/2 top-full mt-2 -translate-x-1/2 whitespace-nowrap rounded-sm bg-ink/95 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-bone opacity-0 transition-opacity duration-200 group-hover:opacity-100">${cafe.name}</span>
  `
  wrapper.addEventListener("click", (ev) => {
    ev.stopPropagation()
    onClick(ev as MouseEvent)
  })
  return wrapper
}

const cafeNameInitials = (name: string): string => {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase()
  return (parts[0]![0]! + parts[1]![0]!).toUpperCase()
}

/** Walking directions in Google Maps; include user [lng,lat] as origin when known. */
const googleMapsDirectionsUrl = (
  cafe: Cafe,
  userLngLat: [number, number] | null,
): string => {
  const params = new URLSearchParams({
    api: "1",
    destination: `${cafe.lat},${cafe.lng}`,
    travelmode: "walking",
  })
  if (userLngLat) {
    const [lng, lat] = userLngLat
    params.set("origin", `${lat},${lng}`)
  }
  return `https://www.google.com/maps/dir/?${params.toString()}`
}

const buildCafePopupDom = (
  cafe: Cafe,
  userLngLat: [number, number] | null,
): HTMLElement => {
  const root = document.createElement("div")
  root.className =
    "box-border flex w-full min-w-0 max-w-full flex-col gap-1.5 text-left text-ink"

  const frame = document.createElement("div")
  frame.className =
    "relative aspect-[5/4] w-full min-w-0 max-w-full overflow-hidden rounded-md border border-ink/10 bg-bone-deep"

  if (cafe.place_photo_p) {
    const loader = document.createElement("div")
    loader.className =
      "absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-bone-deep transition-opacity duration-300 ease-out"
    loader.setAttribute("role", "status")
    loader.setAttribute("aria-live", "polite")

    const spin = document.createElement("div")
    spin.className =
      "h-6 w-6 shrink-0 rounded-full border-2 border-ink/12 border-t-terracotta border-r-terracotta/35 animate-spin"
    spin.setAttribute("aria-hidden", "true")

    const caption = document.createElement("span")
    caption.className =
      "font-mono text-[9px] uppercase tracking-[0.2em] text-ink/45"
    caption.textContent = "Loading photo"

    loader.appendChild(spin)
    loader.appendChild(caption)

    const img = document.createElement("img")
    img.src = `/places/photo?p=${encodeURIComponent(cafe.place_photo_p)}`
    img.alt = ""
    img.className =
      "relative z-0 block h-full w-full max-w-full object-cover object-center"
    img.loading = "lazy"
    img.decoding = "async"

    let dismissed = false
    const dismissLoader = () => {
      if (dismissed) return
      dismissed = true
      loader.classList.add("pointer-events-none", "opacity-0")
      window.setTimeout(() => loader.remove(), 320)
    }

    img.addEventListener("load", dismissLoader, { once: true })
    img.addEventListener(
      "error",
      () => {
        dismissLoader()
        img.remove()
        const fallback = document.createElement("div")
        fallback.className =
          "flex h-full min-h-[3.25rem] w-full min-w-0 max-w-full items-center justify-center font-display text-lg tracking-tight text-ink/30"
        fallback.textContent = cafeNameInitials(cafe.name)
        frame.appendChild(fallback)
      },
      { once: true },
    )

    frame.appendChild(loader)
    frame.appendChild(img)

    requestAnimationFrame(() => {
      if (img.complete && img.naturalHeight > 0) dismissLoader()
    })
  } else {
    const placeholder = document.createElement("div")
    placeholder.className =
      "flex h-full min-h-[3.25rem] w-full min-w-0 max-w-full items-center justify-center font-display text-lg tracking-tight text-ink/30"
    placeholder.textContent = cafeNameInitials(cafe.name)
    frame.appendChild(placeholder)
  }
  root.appendChild(frame)

  const title = document.createElement("p")
  title.className = "min-w-0 font-display text-[13px] leading-snug text-ink"
  title.textContent = cafe.name
  root.appendChild(title)

  const sub = document.createElement("p")
  sub.className = "text-[9px] font-medium uppercase tracking-[0.14em] text-ink/55"
  sub.textContent = cafe.neighborhood
  root.appendChild(sub)

  const nav = document.createElement("a")
  nav.href = googleMapsDirectionsUrl(cafe, userLngLat)
  nav.target = "_blank"
  nav.rel = "noopener noreferrer"
  nav.setAttribute(
    "aria-label",
    userLngLat
      ? `Navigate to ${cafe.name} from your location in Google Maps`
      : `Navigate to ${cafe.name} in Google Maps`,
  )
  nav.className =
    "inline-flex w-fit max-w-full items-center gap-1.5 border-0 bg-transparent p-0 text-left text-[11px] font-medium text-terracotta underline-offset-2 transition-colors hover:text-terracotta-deep hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-terracotta/35 focus-visible:ring-offset-1 focus-visible:ring-offset-bone"

  const navIcon = document.createElement("span")
  navIcon.className = "inline-flex shrink-0 text-current"
  navIcon.setAttribute("aria-hidden", "true")
  navIcon.innerHTML =
    '<svg class="size-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>'

  const navLabel = document.createElement("span")
  navLabel.textContent = "Navigate"

  nav.appendChild(navIcon)
  nav.appendChild(navLabel)
  root.appendChild(nav)

  const attr = document.createElement("p")
  attr.className = "mt-0 text-[8px] leading-snug text-ink/40"
  attr.textContent = "Photos and listing via Google"
  root.appendChild(attr)

  return root
}

const degenerateRouteAtCenter = (): GeoJSON.Feature<GeoJSON.LineString> => ({
  type: "Feature",
  properties: {},
  geometry: {
    type: "LineString",
    coordinates: [SPLIT_CENTER, SPLIT_CENTER],
  },
})

const removeCafeRouteFromMap = (map: MapboxMap) => {
  if (map.getLayer(CAFE_ROUTE_LAYER_ID)) map.removeLayer(CAFE_ROUTE_LAYER_ID)
  if (map.getLayer(CAFE_ROUTE_HALO_LAYER_ID))
    map.removeLayer(CAFE_ROUTE_HALO_LAYER_ID)
  if (map.getSource(CAFE_ROUTE_SOURCE_ID)) map.removeSource(CAFE_ROUTE_SOURCE_ID)
}

const addCafeRouteToMap = (map: MapboxMap) => {
  if (map.getSource(CAFE_ROUTE_SOURCE_ID)) return
  map.addSource(CAFE_ROUTE_SOURCE_ID, {
    type: "geojson",
    data: degenerateRouteAtCenter(),
  })
  map.addLayer({
    id: CAFE_ROUTE_HALO_LAYER_ID,
    type: "line",
    source: CAFE_ROUTE_SOURCE_ID,
    slot: "middle",
    paint: {
      "line-color": "#0e2a3d",
      "line-width": 6,
      "line-opacity": 0.32,
      "line-occlusion-opacity": 0,
      "line-blur": 0.5,
    },
  })
  map.addLayer({
    id: CAFE_ROUTE_LAYER_ID,
    type: "line",
    source: CAFE_ROUTE_SOURCE_ID,
    slot: "middle",
    paint: {
      "line-color": "#0e2a3d",
      "line-width": 3,
      "line-opacity": 0.88,
      "line-occlusion-opacity": 0,
    },
  })
}

const setCafeRouteCoordinates = (
  map: MapboxMap,
  coordinates: [number, number][],
) => {
  const src = map.getSource(CAFE_ROUTE_SOURCE_ID) as GeoJSONSource | undefined
  if (!src) return
  src.setData({
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates },
  })
}

/** Mapbox Directions API walking profile; falls back to a straight segment on error. */
const fetchWalkingRouteLeg = async (
  from: [number, number],
  to: [number, number],
  accessToken: string,
): Promise<[number, number][]> => {
  if (!accessToken) return [from, to]
  const segment = `${from[0]},${from[1]};${to[0]},${to[1]}`
  try {
    const url = new URL(
      `https://api.mapbox.com/directions/v5/mapbox/walking/${segment}`,
    )
    url.searchParams.set("geometries", "geojson")
    url.searchParams.set("overview", "full")
    url.searchParams.set("access_token", accessToken)
    const res = await fetch(url.toString())
    if (!res.ok) return [from, to]
    const json = (await res.json()) as {
      routes?: { geometry?: { coordinates?: [number, number][] } }[]
    }
    const coords = json.routes?.[0]?.geometry?.coordinates
    if (!coords || coords.length < 2) return [from, to]
    return coords
  } catch {
    return [from, to]
  }
}

const walkingRouteDisplayEnd = async (
  from: [number, number],
  cafe: Cafe,
  accessToken: string,
): Promise<[number, number]> => {
  const leg = await fetchWalkingRouteLeg(
    from,
    [cafe.lng, cafe.lat],
    accessToken,
  )
  const last = leg[leg.length - 1]
  return last ?? [cafe.lng, cafe.lat]
}

/** Hide every symbol layer so the basemap stays texture-only (no text/icons). */
const hideAllSymbolLayers = (map: MapboxMap) => {
  map.getStyle().layers?.forEach((layer) => {
    if (layer.type !== "symbol") return
    try {
      map.setLayoutProperty(layer.id, "visibility", "none")
    } catch {
      // Mapbox Standard imports can expose read-only internals; ignore those.
    }
  })
}

const MapPanel = forwardRef<MapPanelHandle, Props>(function MapPanel(
  { onReady, onCafeClick },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapboxMap | null>(null)
  const shadeRef = useRef<ShadeMapHandle | null>(null)
  const markersRef = useRef<Marker[]>([])
  /** Display position per cafe (walking route snap end — matches path terminus). */
  const cafeMarkerLngLatRef = useRef<Map<string, [number, number]>>(new Map())
  /** Invalidates in-flight marker placement when results clear or update. */
  const cafeMarkersGenerationRef = useRef(0)
  const popupRef = useRef<Popup | null>(null)
  const onCafeClickRef = useRef(onCafeClick)
  /** Latest WGS84 fix for walking directions (updated via watchPosition). */
  const userLngLatRef = useRef<[number, number] | null>(null)
  const [showLoadOverlay, setShowLoadOverlay] = useState(true)
  const [status, setStatus] = useState<MapStatus>(() =>
    MAPBOX_TOKEN ? "loading" : "no-token"
  )

  useEffect(() => {
    onCafeClickRef.current = onCafeClick
  }, [onCafeClick])

  useEffect(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const ll: [number, number] = [
          pos.coords.longitude,
          pos.coords.latitude,
        ]
        userLngLatRef.current = ll
      },
      () => {
        userLngLatRef.current = null
      },
      {
        enableHighAccuracy: true,
        maximumAge: 10_000,
        timeout: 20_000,
      },
    )
    return () => navigator.geolocation.clearWatch(watchId)
  }, [])

  useEffect(() => {
    if (!MAPBOX_TOKEN) return
    let cancelled = false

    const init = async () => {
      const mapboxgl = (await import("mapbox-gl")).default
      if (cancelled || !containerRef.current) {
        return
      }

      mapboxgl.accessToken = MAPBOX_TOKEN

      const map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/standard",
        config: {
          basemap: {
            lightPreset: "day",
            theme: "default",
            showPointOfInterestLabels: false,
            showRoadLabels: false,
            showTransitLabels: false,
            showPlaceLabels: false,
            showPedestrianRoads: true,
            show3dObjects: true,
            show3dBuildings: true,
            show3dFacades: true,
            show3dTrees: true,
            show3dLandmarks: true,
            showLandmarkIcons: false,
            showLandmarkIconLabels: false,
            showIndoorLabels: false
          }
        },
        center: SPLIT_CENTER,
        zoom: 16.1,
        minZoom: 12,
        pitch: 52,
        bearing: -18,
        antialias: true,
        attributionControl: true
      })

      mapRef.current = map

      map.on("error", (e) => {
        const msg = e?.error?.message ?? ""
        if (
          msg.toLowerCase().includes("access token") ||
          msg.toLowerCase().includes("unauthorized") ||
          msg.includes("401") ||
          msg.includes("403")
        ) {
          if (!cancelled) setStatus("invalid-token")
        }
      })

      const handleLoad = () => {
        if (cancelled) return

        map.setLights(standardLights)
        map.setLight({
          position: [1.5, 180, 80],
          color: "white",
          intensity: 0.5
        })
        hideAllSymbolLayers(map)

        map.addLayer(
          {
            id: "fts-3d-buildings",
            source: "composite",
            "source-layer": "building",
            slot: "middle",
            filter: ["==", "extrude", "true"],
            type: "fill-extrusion",
            minzoom: 14,
            paint: {
              "fill-extrusion-color": [
                "interpolate",
                ["linear"],
                ["get", "height"],
                0,
                "#efc995",
                25,
                "#d6874f",
                60,
                "#a85e32"
              ],
              "fill-extrusion-height": [
                "interpolate",
                ["linear"],
                ["zoom"],
                14,
                0,
                15.05,
                ["get", "height"]
              ],
              "fill-extrusion-base": [
                "interpolate",
                ["linear"],
                ["zoom"],
                14,
                0,
                15.05,
                ["get", "min_height"]
              ],
              "fill-extrusion-opacity": 0.92
            }
          }
        )

        addCafeRouteToMap(map)

        if (typeof navigator !== "undefined" && navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const ll: [number, number] = [
                pos.coords.longitude,
                pos.coords.latitude,
              ]
              userLngLatRef.current = ll
            },
            () => {},
            { enableHighAccuracy: false, maximumAge: 60_000, timeout: 20_000 },
          )
        }

        setStatus("ready")
        onReady?.()
        window.setTimeout(() => setShowLoadOverlay(false), 260)

        window.setTimeout(() => {
          if (!cancelled) {
            map.resize()
          }
        }, 60)

        map.once("idle", async () => {
          if (cancelled) return
          if (!SHADEMAP_KEY) {
            return
          }
          try {
            const shade = await createShadeMap(map, {
              apiKey: SHADEMAP_KEY,
              mapboxToken: MAPBOX_TOKEN,
              date: new Date()
            })
            if (cancelled) {
              shade.destroy()
              return
            }
            shadeRef.current = shade
          } catch (err) {
            console.error("ShadeMap init failed:", err)
          }
        })
      }

      map.on("load", handleLoad)
    }

    init().catch((err) => {
      console.error("Map init failed:", err)
      if (!cancelled) setStatus("error")
    })

    return () => {
      cancelled = true
      cafeMarkersGenerationRef.current += 1
      cafeMarkerLngLatRef.current.clear()
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []
      cafeMarkerLngLatRef.current.clear()
      popupRef.current?.remove()
      popupRef.current = null
      shadeRef.current?.destroy()
      shadeRef.current = null
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [onReady])

  useImperativeHandle(
    ref,
    (): MapPanelHandle => {
      const drawUserWalkingRouteToCafe = async (cafe: Cafe) => {
        const map = mapRef.current
        if (!map || !map.isStyleLoaded()) return
        addCafeRouteToMap(map)

        let user = userLngLatRef.current
        if (!user) {
          user = await requestFreshUserLngLat()
          if (user) {
            userLngLatRef.current = user
          }
        }

        const from: [number, number] = user ?? SPLIT_CENTER
        const leg = await fetchWalkingRouteLeg(
          from,
          [cafe.lng, cafe.lat],
          MAPBOX_TOKEN,
        )
        setCafeRouteCoordinates(map, leg)
      }

      return {
      flyTo: (area) =>
        new Promise<void>((resolve) => {
          const map = mapRef.current
          if (!map) {
            resolve()
            return
          }
          map.resize()
          window.setTimeout(() => map.resize(), 350)
          window.setTimeout(() => map.resize(), 760)
          map.flyTo({
            center: area.center,
            zoom: area.zoom,
            pitch: 56,
            bearing: -18,
            speed: 0.9,
            curve: 1.4,
            essential: true
          })
          map.once("idle", () => resolve())
        }),
      awaitMapIdle: () =>
        new Promise<void>((resolve) => {
          const map = mapRef.current
          if (!map) {
            resolve()
            return
          }
          if (map.loaded() && !map.isMoving() && !map.isZooming()) {
            resolve()
            return
          }
          map.once("idle", () => resolve())
        }),
      setShadeDate: async (d) => {
        const shade = shadeRef.current
        if (!shade) return
        await shade.setDateAndAwaitIdle(d)
      },
      setShadeOpacity: (opacity) => {
        shadeRef.current?.setOpacity(opacity)
      },
      sampleSun: async (lng, lat) => {
        const map = mapRef.current
        const shade = shadeRef.current
        if (!map || !shade) return false
        const point = map.project([lng, lat])
        return shade.instance.isPositionInSun(point.x, point.y)
      },
      setResults: (results, preference) => {
        const map = mapRef.current
        if (!map) return
        cafeMarkersGenerationRef.current += 1
        const generation = cafeMarkersGenerationRef.current
        removeCafeRouteFromMap(map)
        markersRef.current.forEach((m) => m.remove())
        markersRef.current = []
        cafeMarkerLngLatRef.current.clear()
        popupRef.current?.remove()

        const lngLatForCafe = (cafe: Cafe): [number, number] =>
          cafeMarkerLngLatRef.current.get(cafe.id) ?? [cafe.lng, cafe.lat]

        const openCafePopup = async (cafe: Cafe) => {
          const mapboxgl = (await import("mapbox-gl")).default
          const m = mapRef.current
          if (!m) return
          let origin = userLngLatRef.current
          if (!origin) {
            origin = await requestFreshUserLngLat()
            if (origin) userLngLatRef.current = origin
          }
          if (!popupRef.current) {
            popupRef.current = new mapboxgl.Popup(CAFE_POPUP_OPTIONS)
          }
          popupRef.current
            .setLngLat(lngLatForCafe(cafe))
            .setDOMContent(buildCafePopupDom(cafe, origin))
            .addTo(m)
          onCafeClickRef.current?.(cafe)
          await drawUserWalkingRouteToCafe(cafe)
        }

        const setupMarkers = async () => {
          const mapboxgl = (await import("mapbox-gl")).default

          let user = userLngLatRef.current
          if (!user) {
            user = await requestFreshUserLngLat()
            if (user) userLngLatRef.current = user
          }
          const from: [number, number] = user ?? SPLIT_CENTER

          await Promise.all(
            results.map(async (r) => {
              const end = await walkingRouteDisplayEnd(
                from,
                r.cafe,
                MAPBOX_TOKEN,
              )
              if (generation !== cafeMarkersGenerationRef.current) return

              cafeMarkerLngLatRef.current.set(r.cafe.id, end)

              const el = makeMarkerEl(r.cafe, r.matches, preference, () => {
                void openCafePopup(r.cafe)
              })
              const marker = new mapboxgl.Marker({
                element: el,
                anchor: "center",
              })
                .setLngLat(end)
                .addTo(map)
              markersRef.current.push(marker)
            }),
          )
        }
        void setupMarkers()
      },
      clearResults: () => {
        cafeMarkersGenerationRef.current += 1
        cafeMarkerLngLatRef.current.clear()
        const map = mapRef.current
        if (map) {
          removeCafeRouteFromMap(map)
        }
        markersRef.current.forEach((m) => m.remove())
        markersRef.current = []
        popupRef.current?.remove()
      },
      focusCafe: async (cafe) => {
        const lngLat =
          cafeMarkerLngLatRef.current.get(cafe.id) ?? [cafe.lng, cafe.lat]
        mapRef.current?.resize()
        mapRef.current?.flyTo({
          center: lngLat,
          zoom: 18.2,
          pitch: 60,
          speed: 1.1,
          essential: true
        })
        const mapboxgl = (await import("mapbox-gl")).default
        const map = mapRef.current
        if (!map) return
        let origin = userLngLatRef.current
        if (!origin) {
          origin = await requestFreshUserLngLat()
          if (origin) userLngLatRef.current = origin
        }
        if (!popupRef.current) {
          popupRef.current = new mapboxgl.Popup(CAFE_POPUP_OPTIONS)
        }
        popupRef.current
          .setLngLat(lngLat)
          .setDOMContent(buildCafePopupDom(cafe, origin))
          .addTo(map)
        await drawUserWalkingRouteToCafe(cafe)
      },
      resize: () => {
        mapRef.current?.resize()
      },
    }
  },
  []
  )

  return (
    <div className="relative h-full w-full overflow-visible">
      <div ref={containerRef} className="absolute inset-0 z-0 h-full w-full" />
      <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-terracotta/15" />
      {showLoadOverlay && <StatusOverlay status={status} />}
    </div>
  )
})

const StatusOverlay = ({ status }: { status: MapStatus }) => {
  const isLoading = status === "loading"
  const isMissing = status === "no-token" || status === "no-shademap-key"
  const isInvalid = status === "invalid-token"
  const isReady = status === "ready"
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "absolute inset-0 z-30 flex items-center justify-center bg-bone transition-opacity duration-200 ease-out will-change-opacity",
        isReady ? "pointer-events-none opacity-0" : "opacity-100"
      )}
    >
      <div
        className={cn(
          "grain relative max-w-md px-10 py-12 text-center transition-opacity duration-150 ease-out will-change-opacity",
          isReady ? "opacity-0" : "opacity-100"
        )}
      >
        {isInvalid && (
          <>
            <p className="font-display text-3xl text-ink">
              Mapbox rejected that token
            </p>
            <p className="mt-3 text-sm text-ink-soft">
              <code className="font-mono text-ink">NEXT_PUBLIC_MAPBOX_TOKEN</code>{" "}
              loaded fine, but Mapbox returned 401/403. Common causes:
            </p>
            <ul className="mx-auto mt-4 max-w-sm space-y-1.5 text-left text-xs text-ink-soft">
              <li className="flex items-baseline gap-2">
                <span className="text-terracotta">·</span>
                <span>The token was rotated or deleted.</span>
              </li>
              <li className="flex items-baseline gap-2">
                <span className="text-terracotta">·</span>
                <span>
                  URL restrictions on the token don&apos;t include{" "}
                  <code className="font-mono text-ink">localhost</code>.
                </span>
              </li>
              <li className="flex items-baseline gap-2">
                <span className="text-terracotta">·</span>
                <span>
                  It&apos;s a secret token (<code className="font-mono text-ink">sk.*</code>) instead of public (<code className="font-mono text-ink">pk.*</code>).
                </span>
              </li>
            </ul>
            <p className="mt-4 text-[11px] text-ink/55">
              Fix at{" "}
              <span className="underline">account.mapbox.com/access-tokens</span>{" "}
              and restart the dev server.
            </p>
          </>
        )}
        {isLoading && (
          <>
            <div className="mx-auto mb-6 h-12 w-12 fts-sun-spin">
              <SunGlyph />
            </div>
            <p className="font-display text-2xl text-ink">
              Warming the map…
            </p>
            <p className="mt-2 text-sm text-ink-soft/80">
              Loading Split &amp; the surrounding rooftops
            </p>
          </>
        )}
        {isMissing && (
          <>
            <p className="font-display text-3xl text-ink">a couple of keys</p>
            <p className="mt-3 text-sm text-ink-soft">
              Copy <code className="rounded bg-bone-deep px-1.5 py-0.5 text-[12px]">.env.local.example</code>{" "}
              to <code className="rounded bg-bone-deep px-1.5 py-0.5 text-[12px]">.env.local</code> and add
              your free keys:
            </p>
            <ul className="mx-auto mt-5 max-w-sm space-y-2 text-left text-xs text-ink-soft">
              {!MAPBOX_TOKEN && (
                <li className="flex items-baseline gap-2">
                  <span className="text-terracotta">·</span>
                  <span>
                    <code className="font-mono text-ink">NEXT_PUBLIC_MAPBOX_TOKEN</code> —
                    grab from <span className="underline">account.mapbox.com</span>
                  </span>
                </li>
              )}
              {!SHADEMAP_KEY && (
                <li className="flex items-baseline gap-2">
                  <span className="text-terracotta">·</span>
                  <span>
                    <code className="font-mono text-ink">NEXT_PUBLIC_SHADEMAP_API_KEY</code> —
                    free key at <span className="underline">shademap.app/about</span>
                  </span>
                </li>
              )}
            </ul>
          </>
        )}
        {status === "error" && (
          <>
            <p className="font-display text-2xl text-ink">
              the map couldn&apos;t start
            </p>
            <p className="mt-2 text-sm text-ink-soft">
              Check your console — most often this is an expired Mapbox token or a
              ShadeMap key with no quota left.
            </p>
          </>
        )}
      </div>
    </div>
  )
}

export default MapPanel
