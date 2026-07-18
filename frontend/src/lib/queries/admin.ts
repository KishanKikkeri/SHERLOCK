import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api-client'
import type { Role, UserOut } from '@/lib/types'

export function useAdminUsers() {
  return useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => apiFetch<UserOut[]>('/admin/users'),
  })
}

export function useGrantRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: Role }) =>
      apiFetch(`/admin/users/${userId}/roles?role=${role}`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })
}

export function useRevokeRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: Role }) =>
      apiFetch(`/admin/users/${userId}/roles/${role}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })
}

export function useSetUserActive() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, active }: { userId: number; active: boolean }) =>
      apiFetch(`/admin/users/${userId}/${active ? 'reactivate' : 'deactivate'}`, {
        method: 'POST',
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })
}
