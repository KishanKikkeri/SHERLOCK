import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { CheckCircle2, XCircle, Info } from 'lucide-react'
import { cn } from '@/lib/cn'

type ToastTone = 'positive' | 'critical' | 'info'
interface Toast {
  id: string
  message: string
  tone: ToastTone
}

interface ToastContextValue {
  show: (message: string, tone?: ToastTone) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const TONE_ICON: Record<ToastTone, typeof CheckCircle2> = {
  positive: CheckCircle2,
  critical: XCircle,
  info: Info,
}

const AUTO_DISMISS_MS = 3500

// Deliberately plain — per 01-DESIGN-SYSTEM.md, "a board card saving, a
// comment posting, a review being approved should not sparkle." Fade +
// slide only, 200ms, no bounce. Used sparingly: confirmation that a
// write actually happened (share, comment, review decision), not for
// every possible interaction.
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const show = useCallback((message: string, tone: ToastTone = 'positive') => {
    const id = `toast_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    setToasts((prev) => [...prev, { id, message, tone }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, AUTO_DISMISS_MS)
  }, [])

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => {
          const Icon = TONE_ICON[t.tone]
          return (
            <div
              key={t.id}
              // role="status" (not <output>, which is form-result semantics,
              // wrong fit for a toast) is the standard accessible pattern for
              // transient notifications — announced by screen readers without
              // stealing focus.
              // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
              role="status"
              className={cn(
                'pointer-events-auto flex items-center gap-2 rounded-md border bg-surface px-3 py-2 text-xs shadow-lg',
                'animate-[toast-in_200ms_ease-out]',
                t.tone === 'positive' && 'border-positive/30 text-positive',
                t.tone === 'critical' && 'border-critical/30 text-critical',
                t.tone === 'info' && 'border-info/30 text-info',
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="text-text">{t.message}</span>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
