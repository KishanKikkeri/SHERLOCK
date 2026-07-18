import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-lg border border-border bg-surface', className)}
      {...props}
    />
  )
}

export function CardHeader({
  title,
  action,
  className,
}: {
  title: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between border-b border-border px-4 py-3',
        className,
      )}
    >
      <h2 className="text-sm font-semibold text-text">{title}</h2>
      {action}
    </div>
  )
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4', className)} {...props} />
}

export function EmptyState({
  icon,
  title,
  description,
}: {
  icon: ReactNode
  title: string
  description: string
}) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-center">
      <div className="text-muted" aria-hidden>
        {icon}
      </div>
      <p className="text-sm font-medium text-text">{title}</p>
      <p className="max-w-xs text-xs text-muted">{description}</p>
    </div>
  )
}
