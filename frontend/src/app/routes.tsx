import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage } from '@/auth/LoginPage'
import { RequirePermission } from '@/auth/RequirePermission'
import { AppShell } from '@/components/layout/AppShell'
import { DashboardPage } from '@/dashboard/DashboardPage'
import { InvestigationsListPage } from '@/investigations/InvestigationsListPage'
import { InvestigationDetailPage } from '@/investigations/InvestigationDetailPage'
import { UsersPage } from '@/admin/UsersPage'
import { AuditLogPage } from '@/admin/AuditLogPage'
import { GovernancePage } from '@/admin/GovernancePage'
import { GraphPage } from '@/graph/GraphPage'
import { InvestigationBoardPage } from '@/board/InvestigationBoardPage'
import { VoicePage } from '@/voice/VoicePage'
import { FindingsPage } from '@/findings/FindingsPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequirePermission />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          <Route element={<RequirePermission permission="view_case" />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/investigations" element={<InvestigationsListPage />} />
            <Route path="/investigations/:id" element={<InvestigationDetailPage />} />
            <Route path="/investigations/:id/board" element={<InvestigationBoardPage />} />
            <Route path="/investigations/:id/findings" element={<FindingsPage />} />
            <Route path="/graph" element={<GraphPage />} />
            <Route path="/graph/:personId" element={<GraphPage />} />
          </Route>

          <Route element={<RequirePermission permission="use_voice" />}>
            <Route path="/voice" element={<VoicePage />} />
          </Route>

          <Route element={<RequirePermission permission="manage_users" />}>
            <Route path="/admin/users" element={<UsersPage />} />
          </Route>

          <Route element={<RequirePermission permission="view_audit" />}>
            <Route path="/admin/audit" element={<AuditLogPage />} />
          </Route>

          <Route element={<RequirePermission permission="administer_system" />}>
            <Route path="/admin/governance" element={<GovernancePage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
