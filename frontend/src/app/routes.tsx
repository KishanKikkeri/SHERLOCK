import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage } from '@/auth/LoginPage'
import { RequirePermission } from '@/auth/RequirePermission'
import { AppShell } from '@/components/layout/AppShell'
import { DashboardPage } from '@/dashboard/DashboardPage'
import { PageLoading } from '@/components/layout/PageLoading'
import { RouteErrorBoundary } from '@/components/layout/RouteErrorBoundary'

// Route-level code splitting. Dashboard/Login stay eager (first-paint
// critical path for every session); everything else — especially the
// graph and board, which pull in d3 — is lazy so the initial bundle
// doesn't pay for screens a given session may never visit. Flagged as
// a to-do since F1's validation report; this is where it actually
// gets done, once Vite's own build output started warning about chunk
// size (F5) rather than on a hunch.
const InvestigationsListPage = lazy(() =>
  import('@/investigations/InvestigationsListPage').then((m) => ({ default: m.InvestigationsListPage })),
)
const InvestigationDetailPage = lazy(() =>
  import('@/investigations/InvestigationDetailPage').then((m) => ({ default: m.InvestigationDetailPage })),
)
const InvestigationBoardPage = lazy(() =>
  import('@/board/InvestigationBoardPage').then((m) => ({ default: m.InvestigationBoardPage })),
)
const FindingsPage = lazy(() => import('@/findings/FindingsPage').then((m) => ({ default: m.FindingsPage })))
const GraphPage = lazy(() => import('@/graph/GraphPage').then((m) => ({ default: m.GraphPage })))
const VoicePage = lazy(() => import('@/voice/VoicePage').then((m) => ({ default: m.VoicePage })))
const AnalyticsPage = lazy(() => import('@/analytics/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })))
const UsersPage = lazy(() => import('@/admin/UsersPage').then((m) => ({ default: m.UsersPage })))
const AuditLogPage = lazy(() => import('@/admin/AuditLogPage').then((m) => ({ default: m.AuditLogPage })))
const GovernancePage = lazy(() => import('@/admin/GovernancePage').then((m) => ({ default: m.GovernancePage })))

function Lazy({ children }: { children: React.ReactNode }) {
  return (
    <RouteErrorBoundary>
      <Suspense fallback={<PageLoading />}>{children}</Suspense>
    </RouteErrorBoundary>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequirePermission />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          <Route element={<RequirePermission permission="view_case" />}>
            <Route path="/dashboard" element={<RouteErrorBoundary><DashboardPage /></RouteErrorBoundary>} />
            <Route path="/investigations" element={<Lazy><InvestigationsListPage /></Lazy>} />
            <Route path="/investigations/:id" element={<Lazy><InvestigationDetailPage /></Lazy>} />
            <Route path="/investigations/:id/board" element={<Lazy><InvestigationBoardPage /></Lazy>} />
            <Route path="/investigations/:id/findings" element={<Lazy><FindingsPage /></Lazy>} />
            <Route path="/graph" element={<Lazy><GraphPage /></Lazy>} />
            <Route path="/graph/:personId" element={<Lazy><GraphPage /></Lazy>} />
            <Route path="/analytics" element={<Lazy><AnalyticsPage /></Lazy>} />
          </Route>

          <Route element={<RequirePermission permission="use_voice" />}>
            <Route path="/voice" element={<Lazy><VoicePage /></Lazy>} />
          </Route>

          <Route element={<RequirePermission permission="manage_users" />}>
            <Route path="/admin/users" element={<Lazy><UsersPage /></Lazy>} />
          </Route>

          <Route element={<RequirePermission permission="view_audit" />}>
            <Route path="/admin/audit" element={<Lazy><AuditLogPage /></Lazy>} />
          </Route>

          <Route element={<RequirePermission permission="administer_system" />}>
            <Route path="/admin/governance" element={<Lazy><GovernancePage /></Lazy>} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
