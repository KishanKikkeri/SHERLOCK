import { forwardRef, useId, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  helperText?: string
  error?: string
}

// Height matches Button's `md` size (h-10) so inputs and buttons line up
// in the same row. The helper/error line reserves its slot (min-h) even
// when empty so a validation message appearing doesn't push content
// below it down — see 01-DESIGN-SYSTEM.md's component-state discipline.
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, helperText, error, id, ...props }, ref) => {
    const generatedId = useId()
    const inputId = id ?? generatedId
    const messageId = `${inputId}-message`

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-text">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={!!error}
          aria-describedby={error || helperText ? messageId : undefined}
          className={cn(
            'h-10 w-full rounded-md border bg-surface px-3 text-sm text-text placeholder:text-muted',
            'transition-colors duration-150 outline-none',
            'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
            error ? 'border-critical' : 'border-border',
            className,
          )}
          {...props}
        />
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
Input.displayName = 'Input'
