import type { Permission, Role } from './types'

// Mirrors backend/security/permissions.py ROLE_PERMISSIONS exactly.
// Do not gate the UI on role name string-matching — always go through
// hasPermission() against this table, same as the server does.
const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  administrator: [
    'view_case',
    'participate_case',
    'manage_case',
    'decide_review',
    'use_voice',
    'run_investigation',
    'export_pdf',
    'view_audit',
    'manage_users',
    'administer_system',
  ],
  supervisor: [
    'view_case',
    'participate_case',
    'manage_case',
    'decide_review',
    'use_voice',
    'run_investigation',
    'export_pdf',
    'view_audit',
  ],
  investigator: [
    'view_case',
    'participate_case',
    'manage_case',
    'use_voice',
    'run_investigation',
    'export_pdf',
  ],
  analyst: [
    'view_case',
    'participate_case',
    'use_voice',
    'run_investigation',
    'export_pdf',
  ],
  policy_maker: ['view_case', 'view_audit'],
  read_only: ['view_case'],
}

export function permissionsForRoles(roles: Role[]): Set<Permission> {
  const perms = new Set<Permission>()
  for (const role of roles) {
    for (const perm of ROLE_PERMISSIONS[role] ?? []) {
      perms.add(perm)
    }
  }
  return perms
}

export function hasPermission(
  roles: Role[],
  required: Permission | Permission[],
): boolean {
  const granted = permissionsForRoles(roles)
  const requiredList = Array.isArray(required) ? required : [required]
  return requiredList.every((perm) => granted.has(perm))
}
