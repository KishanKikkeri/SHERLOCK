import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { TokenResponse, UserOut } from '@/lib/types'
import { useAuthStore } from '@/store/auth-store'

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      apiFetch<TokenResponse>('/auth/login', {
        method: 'POST',
        body: credentials,
        skipAuth: true,
        skipRefresh: true,
      }),
    onSuccess: (tokens) => {
      setSession(tokens)
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

export function useMe(enabled: boolean) {
  const setUser = useAuthStore((s) => s.setUser)
  const setAuthMode = useAuthStore((s) => s.setAuthMode)

  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const user = await apiFetch<UserOut>('/auth/me')
      setUser(user)
      setAuthMode('enabled')
      return user
    },
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}

export function useLogout() {
  const clearSession = useAuthStore((s) => s.clearSession)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const refreshToken = useAuthStore.getState().getStoredRefreshToken()
      if (refreshToken) {
        await apiFetch('/auth/logout', {
          method: 'POST',
          body: { refresh_token: refreshToken },
          skipRefresh: true,
        }).catch(() => {
          // Best-effort — clear local session regardless of server outcome.
        })
      }
    },
    onSettled: () => {
      clearSession()
      queryClient.clear()
    },
  })
}
