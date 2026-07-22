import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

/**
 * Tooltip — shows on hover and focus. No JS positioning library;
 * uses CSS absolute positioning relative to the wrapper.
 * Reference: Linear's inline tooltips — minimal, no animation overhead.
 */
export function Tooltip({
  content,
  children,
  side = 'top',
  className,
}: {
  content: ReactNode
  children: ReactNode
  side?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}) {
  const id = useId()

  const sideClasses: Record<string, string> = {
    top: 'bottom-full left-1/2 mb-1.5 -translate-x-1/2',
    bottom: 'top-full left-1/2 mt-1.5 -translate-x-1/2',
    left: 'right-full top-1/2 mr-1.5 -translate-y-1/2',
    right: 'left-full top-1/2 ml-1.5 -translate-y-1/2',
  }

  return (
    <span className="relative inline-flex">
      <span
        tabIndex={0}
        aria-describedby={id}
        className="inline-flex outline-none focus-visible:rounded focus-visible:outline-2 focus-visible:outline-ring"
      >
        {children}
      </span>
      <span
        id={id}
        role="tooltip"
        className={cn(
          'pointer-events-none absolute z-50 whitespace-nowrap rounded-md border border-border bg-surface px-2 py-1 text-xs text-text shadow-md',
          'opacity-0 transition-opacity duration-150',
          'peer-focus:opacity-100',
          sideClasses[side],
          className,
        )}
      >
        {content}
      </span>
    </span>
  )
}
