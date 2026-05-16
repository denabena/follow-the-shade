"use client"

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState
} from "react"
import type { Map as MapboxMap, Marker, StyleSpecification } from "mapbox-gl"
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
  focusCafe: (cafe: Cafe) => void
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

const splitMapStyle: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: [
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"
      ],
      tileSize: 256,
      attribution: "OpenStreetMap contributors"
    },
    composite: {
      type: "vector",
      url: "mapbox://mapbox.mapbox-streets-v8"
    }
  },
  layers: [
    {
      id: "osm-basemap",
      type: "raster",
      source: "osm",
      paint: {
        "raster-saturation": -0.28,
        "raster-contrast": -0.08,
        "raster-brightness-min": 0.05,
        "raster-brightness-max": 0.92
      }
    }
  ]
}

const makeMarkerEl = (
  cafe: Cafe,
  matched: boolean,
  preference: "sun" | "shade" | "either",
  onClick: () => void
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
    <span class="block h-3.5 w-3.5 rounded-full border-2 ${ring} transition-all duration-300 group-hover:scale-125"></span>
    <span class="pointer-events-none absolute left-1/2 top-full mt-2 -translate-x-1/2 whitespace-nowrap rounded-sm bg-ink/95 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-bone opacity-0 transition-opacity duration-200 group-hover:opacity-100">${cafe.name}</span>
  `
  wrapper.addEventListener("click", onClick)
  return wrapper
}

const MapPanel = forwardRef<MapPanelHandle, Props>(function MapPanel(
  { onReady, onCafeClick },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapboxMap | null>(null)
  const shadeRef = useRef<ShadeMapHandle | null>(null)
  const markersRef = useRef<Marker[]>([])
  const onCafeClickRef = useRef(onCafeClick)
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
        style: splitMapStyle,
        center: SPLIT_CENTER,
        zoom: 15.4,
        pitch: 45,
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

        const labelLayer = map
          .getStyle()
          ?.layers?.find(
            (l) => l.type === "symbol" && (l.layout as { [k: string]: unknown })?.["text-field"]
          )

        map.addLayer(
          {
            id: "fts-3d-buildings",
            source: "composite",
            "source-layer": "building",
            filter: ["==", "extrude", "true"],
            type: "fill-extrusion",
            minzoom: 14,
            paint: {
              "fill-extrusion-color": [
                "interpolate",
                ["linear"],
                ["get", "height"],
                0,
                "#e9dcc3",
                25,
                "#d8c4a4",
                60,
                "#c7a87f"
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
              "fill-extrusion-opacity": 0.85
            }
          },
          labelLayer?.id
        )

        setStatus("ready")
        onReady?.()

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
          map.flyTo({
            center: area.center,
            zoom: area.zoom,
            pitch: 50,
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

        const setupMarker = async () => {
          const mapboxgl = (await import("mapbox-gl")).default
          results.forEach((r) => {
            const el = makeMarkerEl(r.cafe, r.matches, preference, () =>
              onCafeClickRef.current?.(r.cafe)
            )
            const marker = new mapboxgl.Marker({
              element: el,
              anchor: "center"
            })
              .setLngLat([r.cafe.lng, r.cafe.lat])
              .addTo(map)
            markersRef.current.push(marker)
          })
        }
        setupMarker()
      },
      clearResults: () => {
        markersRef.current.forEach((m) => m.remove())
        markersRef.current = []
      },
      focusCafe: (cafe) => {
        mapRef.current?.flyTo({
          center: [cafe.lng, cafe.lat],
          zoom: 18.2,
          pitch: 55,
          speed: 1.1,
          essential: true
        })
      }
    }),
    []
  )

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div ref={containerRef} className="absolute inset-0 z-0 h-full w-full" />
      <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-terracotta/15" />
      {status !== "ready" && <StatusOverlay status={status} />}
    </div>
  )
})

const StatusOverlay = ({ status }: { status: MapStatus }) => {
  const isLoading = status === "loading"
  const isMissing = status === "no-token" || status === "no-shademap-key"
  const isInvalid = status === "invalid-token"
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "absolute inset-0 z-10 flex items-center justify-center",
        isLoading ? "bg-bone/30 backdrop-blur-[1px]" : "bg-bone/85 backdrop-blur"
      )}
    >
      <div className="grain relative max-w-md px-10 py-12 text-center">
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
              warming the map…
            </p>
            <p className="mt-2 text-sm text-ink-soft/80">
              loading Split &amp; the surrounding rooftops
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
