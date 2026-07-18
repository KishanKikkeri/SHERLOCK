import { AppProviders } from '@/app/providers'
import { AppRoutes } from '@/app/routes'

function App() {
  return (
    <AppProviders>
      <AppRoutes />
    </AppProviders>
  )
}

export default App
