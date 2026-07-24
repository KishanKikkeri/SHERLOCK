import { ChevronDown, Globe } from 'lucide-react'
import { useLanguage } from '@/providers/LanguageProvider'

const LANGUAGE_LABELS = { en: 'English', kn: 'ಕನ್ನಡ' } as const

/** Global header language toggle. A native <select> rather than a
 * custom popover: fully keyboard/screen-reader accessible for free, and
 * switching is instant (no reload) since it just updates
 * LanguageProvider's state, which every consumer re-renders from. */
export function LanguageToggle() {
  const { language, setLanguage, t } = useLanguage()

  return (
    <div className="relative flex items-center">
      <Globe className="pointer-events-none absolute left-2 h-3.5 w-3.5 text-muted" aria-hidden />
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value as 'en' | 'kn')}
        aria-label={t('navigation.language', 'Language')}
        className="h-8 cursor-pointer appearance-none rounded-md border border-border bg-surface-raised py-0 pl-7 pr-6 text-xs font-medium text-text outline-none transition-colors hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        {(Object.keys(LANGUAGE_LABELS) as Array<keyof typeof LANGUAGE_LABELS>).map((code) => (
          <option key={code} value={code}>
            {LANGUAGE_LABELS[code]}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-1.5 h-3 w-3 text-muted" aria-hidden />
    </div>
  )
}
