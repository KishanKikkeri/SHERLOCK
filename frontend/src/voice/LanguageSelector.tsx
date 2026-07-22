import { useId } from 'react'
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
  const groupName = useId()

  return (
    <div className="flex gap-1.5" role="radiogroup" aria-label="Voice language">
      {languages.map((lang) => (
        <label
          key={lang}
          className={cn(
            'cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors duration-150',
            'has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring',
            value === lang
              ? 'border-accent bg-accent/15 text-accent'
              : 'border-border text-muted hover:bg-surface-raised',
          )}
        >
          <input
            type="radio"
            name={groupName}
            value={lang}
            checked={value === lang}
            onChange={() => onChange(lang)}
            className="sr-only"
          />
          {LANGUAGE_LABELS[lang] ?? lang}
        </label>
      ))}
    </div>
  )
}
