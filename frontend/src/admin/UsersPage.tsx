import { useState } from 'react'
import { Users as UsersIcon, X } from 'lucide-react'
import { Card, CardBody, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'
import {
  useAdminUsers,
  useGrantRole,
  useRevokeRole,
  useSetUserActive,
} from '@/lib/queries/admin'
import type { Role } from '@/lib/types'

const ALL_ROLES: Role[] = [
  'administrator',
  'supervisor',
  'investigator',
  'analyst',
  'policy_maker',
  'read_only',
]

export function UsersPage() {
  const { data: users, isLoading } = useAdminUsers()
  const grantRole = useGrantRole()
  const revokeRole = useRevokeRole()
  const setActive = useSetUserActive()
  const [roleDraft, setRoleDraft] = useState<Record<number, Role>>({})

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold text-text">Users</h1>
        <p className="text-sm text-muted">Manage accounts and role assignments.</p>
      </div>

      <Card>
        <CardBody className="p-0">
          {isLoading ? (
            <div className="flex flex-col gap-2 p-4">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !users || users.length === 0 ? (
            <EmptyState
              icon={<UsersIcon className="h-6 w-6" />}
              title="No users found"
              description="Accounts created via POST /admin/users will appear here."
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="px-4 py-2 font-medium">User</th>
                  <th className="px-4 py-2 font-medium">Roles</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Add role</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {users.map((u) => {
                  const availableToAdd = ALL_ROLES.filter((r) => !u.roles.includes(r))
                  const draft = roleDraft[u.id] ?? availableToAdd[0]
                  return (
                    <tr key={u.id}>
                      <td className="px-4 py-3">
                        <p className="text-text">{u.full_name ?? u.username}</p>
                        <p className="text-xs text-muted">{u.username}</p>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {u.roles.map((r) => (
                            <Badge key={r} tone="info" className="gap-1">
                              {r}
                              <button
                                type="button"
                                aria-label={`Revoke ${r}`}
                                onClick={() => revokeRole.mutate({ userId: u.id, role: r })}
                                className="cursor-pointer rounded-full hover:bg-info/20"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </Badge>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={u.is_active ? 'positive' : 'neutral'}>
                          {u.is_active ? 'Active' : 'Deactivated'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        {availableToAdd.length > 0 && (
                          <div className="flex items-center gap-2">
                            <select
                              className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus-visible:outline-2 focus-visible:outline-ring"
                              value={draft}
                              onChange={(e) =>
                                setRoleDraft((prev) => ({
                                  ...prev,
                                  [u.id]: e.target.value as Role,
                                }))
                              }
                            >
                              {availableToAdd.map((r) => (
                                <option key={r} value={r}>
                                  {r}
                                </option>
                              ))}
                            </select>
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => draft && grantRole.mutate({ userId: u.id, role: draft })}
                            >
                              Add
                            </Button>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          size="sm"
                          variant={u.is_active ? 'destructive' : 'secondary'}
                          onClick={() => setActive.mutate({ userId: u.id, active: !u.is_active })}
                        >
                          {u.is_active ? 'Deactivate' : 'Reactivate'}
                        </Button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
