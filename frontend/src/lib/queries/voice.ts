import { useMutation, useQuery } from '@tanstack/react-query'
import { API_BASE_URL, apiFetch } from '@/lib/api-client'
import { useAuthStore } from '@/store/auth-store'
import type {
  VoiceCommandPhrases,
  VoiceCommandResult,
  VoiceQueryResult,
  VoiceTranscribeResult,
} from '@/lib/types'

export function useSupportedLanguages() {
  return useQuery({
    queryKey: ['language', 'supported'],
    queryFn: () => apiFetch<{ languages: string[] }>('/language/supported', { skipAuth: true, skipRefresh: true }),
    staleTime: Infinity,
  })
}

export function useVoiceCommandPhrases() {
  return useQuery({
    queryKey: ['language', 'voice-commands'],
    queryFn: () => apiFetch<VoiceCommandPhrases>('/language/voice-commands', { skipAuth: true, skipRefresh: true }),
    staleTime: Infinity,
  })
}

// Path A — browser already did STT, just send the text.
export function useVoiceCommand() {
  return useMutation({
    mutationFn: (body: { transcript: string; session_id?: number }) =>
      apiFetch<VoiceCommandResult>('/voice/command', { method: 'POST', body }),
  })
}

// Path B — server-side STT/TTS (Kannada fallback). Multipart, so this
// bypasses apiFetch's JSON body handling and builds the request by hand.
export function useVoiceQuery() {
  return useMutation({
    mutationFn: async ({
      audioBlob,
      sessionId,
      languageHint,
    }: {
      audioBlob: Blob
      sessionId?: number
      languageHint?: string
    }) => {
      const form = new FormData()
      form.append('audio', audioBlob, 'query.webm')
      if (sessionId !== undefined) form.append('session_id', String(sessionId))
      if (languageHint) form.append('language_hint', languageHint)

      const accessToken = useAuthStore.getState().accessToken
      const res = await fetch(`${API_BASE_URL}/voice/query`, {
        method: 'POST',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
        body: form,
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        throw { status: res.status, detail: detail.detail ?? res.statusText }
      }
      return (await res.json()) as VoiceQueryResult
    },
  })
}

export function useVoiceTranscribe() {
  return useMutation({
    mutationFn: async ({ audioBlob, languageHint }: { audioBlob: Blob; languageHint?: string }) => {
      const form = new FormData()
      form.append('audio', audioBlob, 'clip.webm')
      if (languageHint) form.append('language_hint', languageHint)

      const accessToken = useAuthStore.getState().accessToken
      const res = await fetch(`${API_BASE_URL}/voice/transcribe`, {
        method: 'POST',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
        body: form,
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        throw { status: res.status, detail: detail.detail ?? res.statusText }
      }
      return (await res.json()) as VoiceTranscribeResult
    },
  })
}

// Returns an object URL the caller must revoke when done playing.
export function useSpeak() {
  return useMutation({
    mutationFn: async ({ text, language }: { text: string; language: string }) => {
      const accessToken = useAuthStore.getState().accessToken
      const res = await fetch(`${API_BASE_URL}/voice/speak`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ text, language }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        throw { status: res.status, detail: detail.detail ?? res.statusText }
      }
      const provider = res.headers.get('X-TTS-Provider')
      const blob = await res.blob()
      return { url: URL.createObjectURL(blob), provider }
    },
  })
}
