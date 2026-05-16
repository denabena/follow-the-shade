import type { Map as MapboxMap, MapboxGeoJSONFeature } from "mapbox-gl"
import type ShadeMap from "mapbox-gl-shadow-simulator"

type ShadeMapInstance = InstanceType<typeof ShadeMap>

export type ShadeMapHandle = {
  instance: ShadeMapInstance
  setDateAndAwaitIdle: (d: Date) => Promise<void>
  setOpacity: (opacity: number) => void
  destroy: () => void
}

const buildingsFromComposite = (
  map: MapboxMap
): MapboxGeoJSONFeature[] => {
  if (!map.loaded()) return []
  return map
    .querySourceFeatures("composite", { sourceLayer: "building" })
    .filter((f) => {
      const props = f.properties as Record<string, unknown> | null
      if (!props) return false
      if (props.underground === "true") return false
      return Boolean(props.height ?? props.render_height)
    })
}

export const createShadeMap = async (
  map: MapboxMap,
  options: { apiKey: string; mapboxToken: string; date: Date }
): Promise<ShadeMapHandle> => {
  const mod = await import("mapbox-gl-shadow-simulator")
  const ShadeMapCtor = mod.default

  const useMapboxTerrain = Boolean(options.mapboxToken)

  const terrainSource = useMapboxTerrain
    ? {
        tileSize: 514,
        maxZoom: 14,
        getSourceUrl: ({ x, y, z }: { x: number; y: number; z: number }) => {
          const subdomain = (["a", "b", "c", "d"] as const)[(x + y) % 4]
          return `https://${subdomain}.tiles.mapbox.com/raster/v1/mapbox.mapbox-terrain-dem-v1/${z}/${x}/${y}.webp?sku=101wuwGrczDtH&access_token=${options.mapboxToken}`
        },
        getElevation: ({ r, g, b }: { r: number; g: number; b: number }) =>
          -10000 + (r * 256 * 256 + g * 256 + b) * 0.1
      }
    : {
        tileSize: 256,
        maxZoom: 15,
        getSourceUrl: ({ x, y, z }: { x: number; y: number; z: number }) =>
          `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${y}.png`,
        getElevation: ({ r, g, b }: { r: number; g: number; b: number }) =>
          r * 256 + g + b / 256 - 32768
      }

  const instance = new ShadeMapCtor({
    apiKey: options.apiKey,
    date: options.date,
    color: "#07182a",
    opacity: 0.55,
    terrainSource,
    getFeatures: async () => buildingsFromComposite(map)
  }).addTo(map)

  const setDateAndAwaitIdle = (d: Date): Promise<void> =>
    new Promise<void>((resolve) => {
      const safety = window.setTimeout(() => resolve(), 4000)
      instance.once("idle", () => {
        window.clearTimeout(safety)
        resolve()
      })
      instance.setDate(d)
    })

  return {
    instance,
    setDateAndAwaitIdle,
    setOpacity: (opacity: number) => {
      instance.setOpacity(opacity)
    },
    destroy: () => {
      instance.remove()
    }
  }
}
