import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'

const buttonVariants = cva(
  // Border reserved at rest (transparent) so focus/hover never shifts layout.
  // Focus ring is `outline`, never `border` — see 01-DESIGN-SYSTEM.md.
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md border border-transparent ' +
    'text-sm font-medium transition-colors duration-150 cursor-pointer ' +
    'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ' +
    'disabled:pointer-events-none disabled:opacity-50 disabled:cursor-not-allowed',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-white hover:bg-accent/90',
        secondary: 'bg-surface-raised text-text border-border hover:bg-surface-raised/70',
        ghost: 'text-text hover:bg-surface-raised',
        destructive: 'bg-critical text-white hover:bg-critical/90',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        md: 'h-10 px-4',
        lg: 'h-11 px-6 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, isLoading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || isLoading}
        aria-busy={isLoading}
        {...props}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
        {children}
      </button>
    )
  },
)
Button.displayName = 'Button'
