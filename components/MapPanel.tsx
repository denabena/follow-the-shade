"use client"

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState
} from "react"
import type {
  LightsSpecification,
  Map as MapboxMap,
  Marker,
  Popup,
} from "mapbox-gl"
import type { Cafe, CafeResult, IntentArea } from "@/lib/types"
import type { ShadeMapHandle } from "@/lib/shademap"
import { createShadeMap } from "@/lib/shademap"
import { cn } from "@/lib/cn"

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
  matched: boolean,
  preference: "sun" | "shade" | "either",
  onClick: (e: MouseEvent) => void
): HTMLElement => {
  const wrapper = document.createElement("button")
  wrapper.type = "button"
  wrapper.setAttribute("aria-label", `${cafe.name}, ${cafe.neighborhood}`)
  wrapper.className = cn(
    "group relative -translate-x-1/2 -translate-y-1/2 cursor-pointer",
    "outline-none focus-visible:ring-2 focus-visible:ring-terracotta"
  )
  const ring = matched
    ? preference === "sun"
      ? "bg-gold-sun border-terracotta-deep shadow-[0_0_18px_2px_rgba(232,181,71,0.55)]"
      : "bg-ink border-terracotta shadow-[0_0_14px_2px_rgba(74,85,102,0.45)]"
    : "bg-bone-soft border-ink-soft/30 opacity-55"
  wrapper.innerHTML = `
    <span class="block h-2.5 w-2.5 rounded-full border ${ring} transition-all duration-300 group-hover:scale-125"></span>
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

const googleMapsUrlForCafe = (cafe: Cafe): string => {
  if (cafe.google_maps_uri) return cafe.google_maps_uri
  const q = encodeURIComponent(`${cafe.name} ${cafe.neighborhood} Split Croatia`)
  return `https://www.google.com/maps/search/?api=1&query=${q}`
}

const buildCafePopupDom = (cafe: Cafe): HTMLElement => {
  const root = document.createElement("div")
  root.className =
    "flex w-64 max-w-[min(18rem,88vw)] flex-col gap-2.5 text-left text-ink"

  const frame = document.createElement("div")
  frame.className =
    "relative aspect-[4/3] w-full overflow-hidden rounded-lg border border-ink/10 bg-bone-deep"

  if (cafe.place_photo_p) {
    const img = document.createElement("img")
    img.src = `/places/photo?p=${encodeURIComponent(cafe.place_photo_p)}`
    img.alt = ""
    img.className = "h-full w-full object-cover"
    img.loading = "lazy"
    img.decoding = "async"
    frame.appendChild(img)
  } else {
    const placeholder = document.createElement("div")
    placeholder.className =
      "flex h-full min-h-[5.5rem] w-full items-center justify-center font-display text-2xl tracking-tight text-ink/30"
    placeholder.textContent = cafeNameInitials(cafe.name)
    frame.appendChild(placeholder)
  }
  root.appendChild(frame)

  const title = document.createElement("p")
  title.className = "font-display text-[17px] leading-snug text-ink"
  title.textContent = cafe.name
  root.appendChild(title)

  const sub = document.createElement("p")
  sub.className = "text-[11px] font-medium uppercase tracking-[0.16em] text-ink/55"
  sub.textContent = cafe.neighborhood
  root.appendChild(sub)

  const link = document.createElement("a")
  link.href = googleMapsUrlForCafe(cafe)
  link.target = "_blank"
  link.rel = "noopener noreferrer"
  link.className =
    "inline-flex w-fit items-center rounded-full border border-ink/25 px-3 py-1.5 text-[10.5px] font-medium uppercase tracking-[0.12em] text-ink/85 transition-colors hover:border-terracotta hover:text-terracotta"
  link.textContent = "Open in Google Maps"
  root.appendChild(link)

  const attr = document.createElement("p")
  attr.className = "mt-0.5 text-[9px] leading-snug text-ink/40"
  attr.textContent = "Photos and listing via Google"
  root.appendChild(attr)

  return root
}

const hideAddressLabels = (map: MapboxMap) => {
  map.getStyle().layers?.forEach((layer) => {
    if (layer.type !== "symbol") return

    const id = layer.id.toLowerCase()
    const sourceLayer =
      "source-layer" in layer
        ? String(layer["source-layer"] ?? "").toLowerCase()
        : ""

    const looksLikeBuildingNumber =
      id.includes("address") ||
      id.includes("house") ||
      id.includes("housenum") ||
      id.includes("building-number") ||
      sourceLayer.includes("address")

    if (!looksLikeBuildingNumber) return

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
  const popupRef = useRef<Popup | null>(null)
  const onCafeClickRef = useRef(onCafeClick)
  const [showLoadOverlay, setShowLoadOverlay] = useState(true)
  const [status, setStatus] = useState<MapStatus>(() =>
    MAPBOX_TOKEN ? "loading" : "no-token"
  )

  useEffect(() => {
    onCafeClickRef.current = onCafeClick
  }, [onCafeClick])

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
            showPointOfInterestLabels: false,
            showRoadLabels: false,
            showTransitLabels: false,
            showPlaceLabels: false,
            show3dObjects: true
          }
        },
        center: SPLIT_CENTER,
        zoom: 16.1,
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
        hideAddressLabels(map)

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
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []
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
    (): MapPanelHandle => ({
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
        markersRef.current.forEach((m) => m.remove())
        markersRef.current = []
        popupRef.current?.remove()

        const openCafePopup = async (cafe: Cafe) => {
          const mapboxgl = (await import("mapbox-gl")).default
          const m = mapRef.current
          if (!m) return
          if (!popupRef.current) {
            popupRef.current = new mapboxgl.Popup({
              offset: 22,
              closeButton: true,
              closeOnClick: true,
              maxWidth: "min(320px, 92vw)"
            })
          }
          popupRef.current
            .setLngLat([cafe.lng, cafe.lat])
            .setDOMContent(buildCafePopupDom(cafe))
            .addTo(m)
          onCafeClickRef.current?.(cafe)
        }

        const setupMarker = async () => {
          const mapboxgl = (await import("mapbox-gl")).default
          results.forEach((r) => {
            const el = makeMarkerEl(r.cafe, r.matches, preference, () => {
              void openCafePopup(r.cafe)
            })
            const marker = new mapboxgl.Marker({
              element: el,
              anchor: "center"
            })
              .setLngLat([r.cafe.lng, r.cafe.lat])
              .addTo(map)
            markersRef.current.push(marker)
          })
        }
        void setupMarker()
      },
      clearResults: () => {
        markersRef.current.forEach((m) => m.remove())
        markersRef.current = []
        popupRef.current?.remove()
      },
      focusCafe: async (cafe) => {
        mapRef.current?.resize()
        mapRef.current?.flyTo({
          center: [cafe.lng, cafe.lat],
          zoom: 18.2,
          pitch: 60,
          speed: 1.1,
          essential: true
        })
        const mapboxgl = (await import("mapbox-gl")).default
        const map = mapRef.current
        if (!map) return
        if (!popupRef.current) {
          popupRef.current = new mapboxgl.Popup({
            offset: 22,
            closeButton: true,
            closeOnClick: true,
            maxWidth: "min(320px, 92vw)"
          })
        }
        popupRef.current
          .setLngLat([cafe.lng, cafe.lat])
          .setDOMContent(buildCafePopupDom(cafe))
          .addTo(map)
      },
      resize: () => {
        mapRef.current?.resize()
      }
    }),
    []
  )

  return (
    <div className="relative h-full w-full overflow-hidden">
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

const SunGlyph = () => (
  <svg viewBox="0 0 48 48" className="h-full w-full" aria-hidden="true">
    <circle cx="24" cy="24" r="7" fill="#e8b547" />
    {[...Array(8)].map((_, i) => {
      const a = (i * Math.PI) / 4
      const x1 = 24 + Math.cos(a) * 12
      const y1 = 24 + Math.sin(a) * 12
      const x2 = 24 + Math.cos(a) * 20
      const y2 = 24 + Math.sin(a) * 20
      return (
        <line
          key={i}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke="#c76b45"
          strokeWidth={2.2}
          strokeLinecap="round"
        />
      )
    })}
  </svg>
)

export default MapPanel
