import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const CHORD_TIMEOUT_MS = 900

const GO_TO: Record<string, string> = {
  d: '/dashboard',
  i: '/investigations',
  g: '/graph',
  v: '/voice',
  a: '/analytics',
}

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable
}

/** Mounted once in AppShell. Returns whether the help overlay should be
 * shown, and a setter to close it — the "?" key opens it, Escape or the
 * overlay's own close button dismiss it. */
export function useKeyboardShortcuts() {
  const navigate = useNavigate()
  const [helpOpen, setHelpOpen] = useState(false)
  const awaitingSecondKey = useRef(false)
  const chordTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return
      if (e.metaKey || e.ctrlKey || e.altKey) return

      if (e.key === 'Escape') {
        setHelpOpen(false)
        return
      }

      if (e.key === '?') {
        e.preventDefault()
        setHelpOpen((v) => !v)
        return
      }

      if (awaitingSecondKey.current) {
        awaitingSecondKey.current = false
        if (chordTimer.current) clearTimeout(chordTimer.current)
        const path = GO_TO[e.key.toLowerCase()]
        if (path) {
          e.preventDefault()
          navigate(path)
        }
        return
      }

      if (e.key === 'g') {
        awaitingSecondKey.current = true
        chordTimer.current = setTimeout(() => {
          awaitingSecondKey.current = false
        }, CHORD_TIMEOUT_MS)
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      if (chordTimer.current) clearTimeout(chordTimer.current)
    }
  }, [navigate])

  return { helpOpen, setHelpOpen }
}

export const SHORTCUT_GROUPS: { keys: string; labelKey: string; fallback: string }[] = [
  { keys: 'g d', labelKey: 'keyboard_shortcuts_panel.go_to_dashboard', fallback: 'Go to Dashboard' },
  { keys: 'g i', labelKey: 'keyboard_shortcuts_panel.go_to_investigations', fallback: 'Go to Investigations' },
  { keys: 'g g', labelKey: 'keyboard_shortcuts_panel.go_to_network_graph', fallback: 'Go to Network graph' },
  { keys: 'g v', labelKey: 'keyboard_shortcuts_panel.go_to_voice', fallback: 'Go to Voice' },
  { keys: 'g a', labelKey: 'keyboard_shortcuts_panel.go_to_analytics', fallback: 'Go to Analytics' },
  { keys: '?', labelKey: 'keyboard_shortcuts_panel.show_this_help', fallback: 'Show this help' },
  { keys: 'Esc', labelKey: 'keyboard_shortcuts_panel.close_dialogs', fallback: 'Close dialogs / deselect' },
]
