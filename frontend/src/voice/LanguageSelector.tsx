import { useSupportedLanguages } from '@/lib/queries/voice'
import { cn } from '@/lib/cn'

const LANGUAGE_LABELS: Record<string, string> = {
  en: 'English',
  kn: 'ಕನ್ನಡ (Kannada)',
}

export function LanguageSelector({
  value,
  onChange,
}: {
  value: string
  onChange: (lang: string) => void
}) {
  const { data } = useSupportedLanguages()
  const languages = data?.languages ?? ['en', 'kn']

  return (
    <div className="flex gap-1.5" role="radiogroup" aria-label="Voice language">
      {languages.map((lang) => (
        <button
          key={lang}
          type="button"
          role="radio"
          aria-checked={value === lang}
          onClick={() => onChange(lang)}
          className={cn(
            'cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors duration-150',
            value === lang
              ? 'border-accent bg-accent/15 text-accent'
              : 'border-border text-muted hover:bg-surface-raised',
          )}
        >
          {LANGUAGE_LABELS[lang] ?? lang}
        </button>
      ))}
    </div>
  )
}
