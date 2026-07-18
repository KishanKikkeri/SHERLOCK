import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/cn'

// Semantic tones only — these map 1:1 onto 01-DESIGN-SYSTEM.md's status
// tokens. Don't add a new tone per component; reuse these everywhere a
// priority/status/confidence/review-state needs a badge.
const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
  {
    variants: {
      tone: {
        neutral: 'border-border bg-surface-raised text-muted',
        positive: 'border-positive/30 bg-positive/10 text-positive',
        warning: 'border-warning/30 bg-warning/10 text-warning',
        critical: 'border-critical/30 bg-critical/10 text-critical',
        info: 'border-info/30 bg-info/10 text-info',
      },
    },
    defaultVariants: {
      tone: 'neutral',
    },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
