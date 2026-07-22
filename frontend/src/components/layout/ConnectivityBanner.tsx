import { WifiOff, ServerCrash } from 'lucide-react'
import { useOnlineStatus } from '@/lib/use-online-status'
import { useHealth } from '@/lib/queries/system'

export function ConnectivityBanner() {
  const isOnline = useOnlineStatus()
  const { isError: backendUnreachable, data } = useHealth()

  if (!isOnline) {
    return (
      <div className="flex items-center justify-center gap-2 bg-critical py-1.5 text-xs font-medium text-white">
        <WifiOff className="h-3.5 w-3.5" aria-hidden />
        You're offline — check your connection. Changes won't save until it's back.
      </div>
    )
  }

  // Only warn once we've actually confirmed the backend is unreachable
  // (not merely "still loading") — distinct message from "you're
  // offline" since the fix is different (this isn't the user's network).
  if (backendUnreachable || data?.status === 'down') {
    return (
      <div className="flex items-center justify-center gap-2 bg-warning py-1.5 text-xs font-medium text-background">
        <ServerCrash className="h-3.5 w-3.5" aria-hidden />
        Can't reach the SHERLOCK backend — your connection is fine, the server isn't responding.
      </div>
    )
  }

  return null
}
