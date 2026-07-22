import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface TabItem {
  label: string
  value: string
  count?: number
}

export function Tabs({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem[]
  value: string
  onChange: (value: string) => void
  className?: string
}) {
  const groupId = useId()

  return (
    <div
      role="tablist"
      aria-label={groupId}
      className={cn('flex items-center gap-1 border-b border-border', className)}
    >
      {items.map((item) => {
        const active = item.value === value
        return (
          <button
            key={item.value}
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(item.value)}
            className={cn(
              'flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors duration-150',
              'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
              active
                ? 'border-accent text-text'
                : 'border-transparent text-muted hover:text-text',
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.5 text-2xs font-semibold',
                  active
                    ? 'bg-accent/15 text-accent'
                    : 'bg-surface-raised text-muted',
                )}
              >
                {item.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export function TabPanel({
  value,
  active,
  children,
  className,
}: {
  value: string
  active: string
  children: ReactNode
  className?: string
}) {
  if (value !== active) return null
  return (
    <div
      role="tabpanel"
      className={cn('animate-[fade-in_var(--dur-fast)_var(--ease-out)]', className)}
    >
      {children}
    </div>
  )
}
