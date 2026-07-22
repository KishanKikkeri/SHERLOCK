import { forwardRef, useId, type SelectHTMLAttributes } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/cn'

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  helperText?: string
  error?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, helperText, error, id, children, ...props }, ref) => {
    const generatedId = useId()
    const selectId = id ?? generatedId
    const messageId = `${selectId}-message`

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={selectId} className="text-sm font-medium text-text">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            aria-invalid={!!error}
            aria-describedby={error || helperText ? messageId : undefined}
            className={cn(
              'h-10 w-full appearance-none rounded-md border bg-surface px-3 pr-9 text-sm text-text',
              'transition-colors duration-150 outline-none',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
              error ? 'border-critical' : 'border-border',
              className,
            )}
            {...props}
          >
            {children}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden
          />
        </div>
        <p
          id={messageId}
          className={cn('min-h-4 text-xs', error ? 'text-critical' : 'text-muted')}
        >
          {error ?? helperText ?? ''}
        </p>
      </div>
    )
  },
)
Select.displayName = 'Select'
