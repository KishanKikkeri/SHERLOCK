import { useEffect, useState } from 'react'
import { Search, X, Loader2, TriangleAlert } from 'lucide-react'
import type { GraphSearchResult } from '@/lib/types'
import { useGraphSearch } from '@/lib/queries/graph'
import { ENTITY_META, entityLabel } from './entity-meta'
import { Input } from '@/components/ui/Input'
import { useLanguage } from '@/providers/LanguageProvider'
import { cn } from '@/lib/cn'

const DEBOUNCE_MS = 250

/**
 * Priority 18-23 — unified graph search. Accepts any natural identifier
 * (name, alias, vehicle number, phone, bank account, weapon serial,
 * FIR/crime number, org/gang name, address, location, district, state,
 * or crime type) and lets the investigator navigate straight to it,
 * without ever choosing an entity type themselves.
 */
export function GraphSearch({
  caseId,
  onSelectResult,
}: {
  /** Currently-selected case (Crime id), if any — boosts ranking for
   * entities already connected to it (Priority 23). */
  caseId?: number
  onSelectResult: (result: GraphSearchResult) => void
}) {
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const { t } = useLanguage()

  useEffect(() => {
    const id = setTimeout(() => setDebounced(query), DEBOUNCE_MS)
    return () => clearTimeout(id)
  }, [query])

  const { data, isFetching, isError } = useGraphSearch(debounced, caseId)
  const results = data?.results ?? []

  return (
    <div className="flex flex-col gap-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
        <Input
          placeholder={t(
            'graph.search_placeholder',
            'Search a name, vehicle, phone, FIR, org, location…',
          )}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9 pr-9"
          aria-label="Search the crime intelligence graph"
        />
        {isFetching && (
          <Loader2 className="absolute right-9 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted" aria-hidden />
        )}
        {query && (
          <button
            type="button"
            onClick={() => setQuery('')}
            aria-label="Clear search"
            className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer text-muted hover:text-text"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {isError && debounced && (
        <p className="flex items-center gap-1.5 text-xs text-critical">
          <TriangleAlert className="h-3.5 w-3.5" /> Search failed — try again.
        </p>
      )}

      {!isError && debounced && !isFetching && results.length === 0 && (
        <p className="text-xs text-muted">No matches for "{debounced}".</p>
      )}

      {results.length > 0 && (
        <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
          {results.map((r) => {
            const isCrimeType = r.type === 'CrimeType'
            const meta = isCrimeType ? null : ENTITY_META[r.type as Exclude<typeof r.type, 'CrimeType'>]
            const Icon = meta?.icon
            return (
              <li key={`${r.type}:${r.id}`}>
                <button
                  type="button"
                  disabled={isCrimeType}
                  onClick={() => {
                    if (isCrimeType) return
                    onSelectResult(r)
                    setQuery('')
                  }}
                  title={isCrimeType ? 'A crime type filters cases — it isn\u2019t a single node to open yet.' : undefined}
                  className={cn(
                    'flex w-full items-center gap-2 px-3 py-2 text-left text-sm',
                    isCrimeType ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:bg-surface-raised',
                  )}
                >
                  {Icon ? (
                    <span
                      className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
                      style={{ backgroundColor: `var(--${meta!.colorVar})` }}
                      aria-hidden
                    >
                      <Icon className="h-3 w-3" style={{ stroke: '#fff' }} strokeWidth={2.5} />
                    </span>
                  ) : (
                    <span className="h-2 w-2 shrink-0 rounded-full bg-muted" aria-hidden />
                  )}
                  <span className="truncate text-text">{r.label}</span>
                  <span className="ml-auto shrink-0 text-xs text-muted">
                    {isCrimeType ? 'Crime type' : entityLabel(r.type as Exclude<typeof r.type, 'CrimeType'>, t)}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
