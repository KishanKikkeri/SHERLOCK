import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
  type ReactNode,
} from 'react'
import { apiFetch } from '@/lib/api-client'

export type UiLanguage = 'en' | 'kn'

const STORAGE_KEY = 'sherlock.language'
const FALLBACK_LANGUAGE: UiLanguage = 'en'

type ResourceBundle = Record<string, Record<string, string>>

interface TranslateResponse {
  text: string
  source_language: string
  target_language: string
  detected_language: string
  confidence: number
  engine: string
  warnings: string[]
}

interface LanguageContextValue {
  language: UiLanguage
  setLanguage: (lang: UiLanguage) => void
  toggleLanguage: () => void
  /** Static UI string lookup, e.g. t('navigation.dashboard'). Falls back
   * to the raw key (or an explicit fallback) if the key or the resource
   * bundle isn't loaded yet — never throws, never blocks render. */
  t: (key: string, fallback?: string) => string
  /** Dynamic AI-output translation (findings, narratives, executive
   * summaries) via the existing POST /language/translate — the ONLY
   * translation call path for this kind of content; never re-implemented
   * client-side. No-ops (returns the input unchanged) when the current
   * UI language already matches `sourceLanguage`, and caches every
   * result in memory so the same text is never sent twice. */
  translateDynamic: (text: string, sourceLanguage?: 'en' | 'kn') => Promise<string>
  resourcesLoading: boolean
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

function getInitialLanguage(): UiLanguage {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'en' || stored === 'kn' ? stored : FALLBACK_LANGUAGE
}

function readByPath(bundle: ResourceBundle | null, key: string): string | undefined {
  if (!bundle) return undefined
  const [section, field] = key.split('.', 2)
  return bundle[section]?.[field]
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<UiLanguage>(getInitialLanguage)
  const [resourcesLoading, setResourcesLoading] = useState(true)

  // One bundle per language, fetched once and kept for the session —
  // switching back and forth never re-fetches.
  const bundleCache = useRef(new Map<UiLanguage, ResourceBundle>())
  const [activeBundle, setActiveBundle] = useState<ResourceBundle | null>(null)

  // Dynamic-translation cache: `${targetLang}::${sourceLang}::${text}` ->
  // translated text. Same AI output is never sent to /language/translate
  // twice, per Phase 4's "never translate twice, cache translated
  // responses" requirement.
  const dynamicCache = useRef(new Map<string, string>())

  const warnedMissingKeys = useRef(new Set<string>())

  useEffect(() => {
    let cancelled = false

    async function loadResources() {
      const cached = bundleCache.current.get(language)
      if (cached) {
        setActiveBundle(cached)
        setResourcesLoading(false)
        return
      }
      setResourcesLoading(true)
      try {
        const bundle = await apiFetch<ResourceBundle>(`/language/resources/${language}`, { skipAuth: true })
        if (cancelled) return
        bundleCache.current.set(language, bundle)
        setActiveBundle(bundle)
      } catch {
        // Backend unreachable or language unsupported — fall back to
        // raw keys via t()'s own fallback rather than a blank UI.
        if (!cancelled) setActiveBundle(null)
      } finally {
        if (!cancelled) setResourcesLoading(false)
      }
    }

    loadResources()
    return () => {
      cancelled = true
    }
  }, [language])

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, language)
    document.documentElement.lang = language
  }, [language])

  const setLanguage = useCallback((lang: UiLanguage) => setLanguageState(lang), [])
  const toggleLanguage = useCallback(
    () => setLanguageState((prev) => (prev === 'en' ? 'kn' : 'en')),
    [],
  )

  const t = useCallback(
    (key: string, fallback?: string): string => {
      const value = readByPath(activeBundle, key)
      if (value !== undefined) return value
      if (import.meta.env.DEV && !warnedMissingKeys.current.has(key)) {
        warnedMissingKeys.current.add(key)
        console.warn(`[LanguageProvider] Missing translation key "${key}" for language "${language}"`)
      }
      return fallback ?? key
    },
    [activeBundle, language],
  )

  const translateDynamic = useCallback(
    async (text: string, sourceLanguage: 'en' | 'kn' = 'en'): Promise<string> => {
      if (!text || !text.trim()) return text
      if (language === sourceLanguage) return text

      const cacheKey = `${language}::${sourceLanguage}::${text}`
      const cached = dynamicCache.current.get(cacheKey)
      if (cached !== undefined) return cached

      try {
        const result = await apiFetch<TranslateResponse>('/language/translate', {
          method: 'POST',
          skipAuth: true,
          body: { text, target_language: language, source_language: sourceLanguage },
        })
        dynamicCache.current.set(cacheKey, result.text)
        return result.text
      } catch {
        // Translation-service failure degrades to the original text —
        // matches the backend's own passthrough behavior, never breaks
        // the page.
        return text
      }
    },
    [language],
  )

  const value = useMemo<LanguageContextValue>(
    () => ({ language, setLanguage, toggleLanguage, t, translateDynamic, resourcesLoading }),
    [language, setLanguage, toggleLanguage, t, translateDynamic, resourcesLoading],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within a LanguageProvider')
  return ctx
}
