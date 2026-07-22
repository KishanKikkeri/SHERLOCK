import { useEffect, useState } from 'react'

/** navigator.onLine only tells you about the network interface, not
 * whether the SHERLOCK backend is actually reachable — that's a
 * separate signal (see HealthStatusBadge / ConnectivityBanner, which
 * combines this with the /health poll already used elsewhere). Keeping
 * them distinct on purpose: "you're offline" and "the backend is down"
 * need different messaging, per 03-COMPONENT-ARCHITECTURE.md's F8 note. */
export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine,
  )

  useEffect(() => {
    const goOnline = () => setIsOnline(true)
    const goOffline = () => setIsOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])

  return isOnline
}
