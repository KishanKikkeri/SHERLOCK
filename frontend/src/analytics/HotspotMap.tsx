/**
 * Real basemap via Leaflet + react-leaflet + leaflet.heat, replacing the
 * earlier lightweight SVG bubble-map — same `heatmap` payload shape
 * (`{lat, lng, weight}`) as before, so this was a frontend-only swap,
 * no backend changes needed (as flagged when the SVG version shipped).
 *
 * Clicking a hotspot marker drills down via GET /analytics/hotspot/{location}
 * (see useHotspotBreakdown) into a crime-type breakdown + monthly timeline
 * for that specific location — scoped to what this agent can honestly
 * answer (see hotspot_engine.location_breakdown's docstring for what's
 * deliberately NOT included, e.g. "nearby offenders").
 */
import { useEffect, useRef, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import type { LatLngExpression } from 'leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet.heat'
import { ChevronDown, MapPinned } from 'lucide-react'
import type { HeatmapPoint, HotspotEntry } from '@/lib/queries/analytics-dashboard'
import { useHotspotBreakdown } from '@/lib/queries/analytics-dashboard'
import { Card, CardHeader, CardBody, EmptyState } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'

function HeatLayer({ points }: { points: HeatmapPoint[] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length === 0) return
    const maxWeight = Math.max(...points.map((p) => p.weight), 1)
    const layer = (L as any).heatLayer(
      points.map((p) => [p.lat, p.lng, p.weight / maxWeight]),
      { radius: 28, blur: 20, maxZoom: 14 },
    )
    layer.addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, points])
  return null
}

function FitBounds({ points }: { points: HeatmapPoint[] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length === 0) return
    const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lng] as LatLngExpression))
    map.fitBounds(bounds, { padding: [24, 24] })
  }, [map, points])
  return null
}

function HotspotDrilldown({ location, onClose }: { location: string; onClose: () => void }) {
  const { data, isLoading } = useHotspotBreakdown(location)

  return (
    <div className="rounded-md border border-border bg-surface-raised p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-text">{location}</p>
        <button type="button" onClick={onClose} className="text-xs text-muted hover:text-text">
          Close
        </button>
      </div>

      {isLoading && <Skeleton className="mt-2 h-24 w-full" />}

      {!isLoading && data && (
        <div className="mt-2 flex flex-col gap-2">
          <p className="text-xs text-muted">{data.total} total incidents · {data.district}</p>
          <div className="flex flex-col gap-1">
            {data.by_crime_type.map((t) => (
              <div key={t.crime_type} className="flex items-center justify-between text-xs">
                <span className="text-text">{t.crime_type.replaceAll('_', ' ')}</span>
                <span className="mono text-muted">{t.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function HotspotMap({
  heatmap,
  topHotspots,
  isLoading,
}: {
  heatmap: HeatmapPoint[] | undefined
  topHotspots: HotspotEntry[] | undefined
  isLoading: boolean
}) {
  const [drilldownLocation, setDrilldownLocation] = useState<string | null>(null)
  const initialCenter = useRef<LatLngExpression>([12.9716, 77.5946]) // Karnataka-ish fallback until points load

  return (
    <Card>
      <CardHeader title="Crime hotspots" subtitle="Click a marker to drill into crime types at that location" />
      <CardBody className="flex flex-col gap-4 lg:flex-row">
        {isLoading && <Skeleton className="h-[360px] w-full" />}

        {!isLoading && (!heatmap || heatmap.length === 0) && (
          <EmptyState icon={<MapPinned className="h-6 w-6" />} title="No hotspots" description="No crimes recorded in the current filter scope." />
        )}

        {!isLoading && heatmap && heatmap.length > 0 && (
          <>
            <div className="h-[360px] w-full max-w-[520px] shrink-0 overflow-hidden rounded-md">
              <MapContainer center={initialCenter.current} zoom={7} className="h-full w-full" scrollWheelZoom={false}>
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <FitBounds points={heatmap} />
                <HeatLayer points={heatmap} />
                {heatmap.map((p) => (
                  <CircleMarker
                    key={p.location}
                    center={[p.lat, p.lng]}
                    radius={6}
                    pathOptions={{ color: 'var(--entity-crime, #f87171)', fillOpacity: 0.7 }}
                    eventHandlers={{ click: () => setDrilldownLocation(p.location) }}
                  >
                    <Popup>
                      {p.location} — {p.weight} crimes
                    </Popup>
                  </CircleMarker>
                ))}
              </MapContainer>
            </div>

            <div className="flex-1 overflow-auto">
              {drilldownLocation ? (
                <HotspotDrilldown location={drilldownLocation} onClose={() => setDrilldownLocation(null)} />
              ) : (
                topHotspots &&
                topHotspots.length > 0 && (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-left text-muted">
                        <th className="pb-1.5 font-medium">Location</th>
                        <th className="pb-1.5 font-medium">District</th>
                        <th className="pb-1.5 text-right font-medium">Count</th>
                        <th className="pb-1.5" aria-label="Expand" />
                      </tr>
                    </thead>
                    <tbody>
                      {topHotspots.map((h) => (
                        <tr
                          key={h.location}
                          className="cursor-pointer border-b border-border-subtle last:border-0 hover:bg-surface-raised"
                          onClick={() => setDrilldownLocation(h.location)}
                        >
                          <td className="py-1.5 text-text">{h.location}</td>
                          <td className="py-1.5 text-muted">{h.district}</td>
                          <td className="mono py-1.5 text-right text-text">{h.count}</td>
                          <td className="py-1.5 text-right text-muted">
                            <ChevronDown className="ml-auto h-3.5 w-3.5" aria-hidden />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              )}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  )
}
