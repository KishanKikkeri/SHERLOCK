import { useState, type FormEvent } from 'react'
import { Search, X } from 'lucide-react'
import type { RawGraphNode } from '@/lib/types'
import { ENTITY_META } from './entity-meta'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'

export function GraphSearch({
  nodes,
  onSelectNode,
  onCenterOnPerson,
}: {
  nodes: RawGraphNode[]
  onSelectNode: (node: RawGraphNode) => void
  onCenterOnPerson: (personId: number) => void
}) {
  const [query, setQuery] = useState('')
  const [personIdInput, setPersonIdInput] = useState('')

  const results =
    query.trim().length > 0
      ? nodes
          .filter((n) => n.label.toLowerCase().includes(query.trim().toLowerCase()))
          .slice(0, 8)
      : []

  function handleCenterSubmit(e: FormEvent) {
    e.preventDefault()
    const id = Number(personIdInput)
    if (Number.isInteger(id) && id > 0) {
      onCenterOnPerson(id)
      setPersonIdInput('')
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
        <Input
          placeholder="Search nodes in this graph…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9"
          aria-label="Search loaded graph nodes"
        />
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

      {results.length > 0 && (
        <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
          {results.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => {
                  onSelectNode(n)
                  setQuery('')
                }}
                className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-raised"
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: `var(--${ENTITY_META[n.type].colorVar})` }}
                  aria-hidden
                />
                <span className="truncate text-text">{n.label}</span>
                <span className="ml-auto shrink-0 text-xs text-muted">{ENTITY_META[n.type].label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleCenterSubmit} className="flex items-end gap-2 border-t border-border pt-3">
        <Input
          label="Center on person ID"
          helperText="No name search exists yet — see known limitations"
          type="number"
          min={1}
          value={personIdInput}
          onChange={(e) => setPersonIdInput(e.target.value)}
          className="w-32"
        />
        <Button type="submit" variant="secondary" size="md">
          Go
        </Button>
      </form>
    </div>
  )
}
