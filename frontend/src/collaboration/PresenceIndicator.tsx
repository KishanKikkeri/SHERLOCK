import { useEffect, useRef } from 'react'
import { Eye, Pencil } from 'lucide-react'
import { useHeartbeatPresence, usePresence } from '@/lib/queries/collaboration'
import { useAuth } from '@/auth/AuthProvider'

const HEARTBEAT_INTERVAL_MS = 20 * 1000

export function PresenceIndicator({
  sessionId,
  editing = false,
}: {
  sessionId: number
  editing?: boolean
}) {
  const { user } = useAuth()
  const { data: presence } = usePresence(sessionId)
  const heartbeat = useHeartbeatPresence(sessionId)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!user?.officer_id) return

    const sendHeartbeat = () => {
      if (document.visibilityState !== 'visible') return
      heartbeat.mutate({ officer_id: user.officer_id!, status: editing ? 'editing' : 'viewing' })
    }

    sendHeartbeat() // immediately on mount/focus, don't wait a full interval
    intervalRef.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS)

    const onVisibility = () => {
      if (document.visibilityState === 'visible') sendHeartbeat()
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      document.removeEventListener('visibilitychange', onVisibility)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, user?.officer_id, editing])

  const others = presence?.filter((p) => p.officer_id !== user?.officer_id) ?? []

  if (others.length === 0) return null

  return (
    <div className="flex items-center gap-1.5" title={`${others.length} other officer(s) here now`}>
      <div className="flex -space-x-1.5">
        {others.slice(0, 5).map((p) => (
          <span
            key={p.officer_id}
            className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface bg-accent/20 text-[10px] font-medium text-accent"
            title={`Officer #${p.officer_id} — ${p.status}`}
          >
            {p.status === 'editing' ? <Pencil className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
          </span>
        ))}
      </div>
      {others.length > 5 && <span className="text-xs text-muted">+{others.length - 5}</span>}
    </div>
  )
}
