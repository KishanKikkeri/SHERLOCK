import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { SHORTCUT_GROUPS } from '@/lib/use-keyboard-shortcuts'
import { Button } from '@/components/ui/Button'
import { useLanguage } from '@/providers/LanguageProvider'

export function KeyboardShortcutsHelp({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const { t } = useLanguage()

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
    // No cleanup call to dialog.close() here: unmounting already removes the
    // node (and its top-layer modal) from the DOM, and calling close()
    // ourselves fires the dialog's native "close" event, which re-enters
    // onClose()/setHelpOpen(false). Under React StrictMode's dev-only
    // double-invoke of effects, that re-entrancy closed the panel in the
    // same tick it opened, so the icon appeared to do nothing.
  }, [])

  return (
    // Native <dialog> opened via showModal() already provides real
    // keyboard handling internally (Escape closes it, focus is trapped
    // inside) — the onClick below is a supplementary mouse-only backdrop-
    // dismiss convenience, the standard documented pattern for this
    // element, not a missing-keyboard-support gap.
    // oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={dialogRef}
      aria-label={t('keyboard_shortcuts_panel.title')}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose()
      }}
      className="m-auto rounded-lg border border-border bg-surface p-0 shadow-xl backdrop:bg-black/40"
    >
      <div className="w-full max-w-sm p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text">{t('keyboard_shortcuts_panel.title')}</h2>
          <Button variant="ghost" size="icon" aria-label={t('common.close')} onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <dl className="flex flex-col gap-2">
          {SHORTCUT_GROUPS.map((s) => (
            <div key={s.keys} className="flex items-center justify-between text-sm">
              <dt className="text-muted">{t(s.labelKey, s.fallback)}</dt>
              <dd className="flex gap-1">
                {s.keys.split(' ').map((k, i) => (
                  <kbd
                    key={i}
                    className="rounded border border-border bg-surface-raised px-1.5 py-0.5 font-mono text-xs text-text"
                  >
                    {k}
                  </kbd>
                ))}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </dialog>
  )
}
