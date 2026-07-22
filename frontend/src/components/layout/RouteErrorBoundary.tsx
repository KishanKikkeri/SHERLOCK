import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertOctagon } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

// Class component is required here — there's no hook equivalent for
// componentDidCatch/getDerivedStateFromError. One instance per lazy
// route boundary (see app/routes.tsx's <Lazy> wrapper), not a single
// app-wide instance, so a crash in one page (e.g. a bad graph render)
// leaves the nav/header/other routes usable rather than blanking
// everything.
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('Route crashed:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-critical/30 bg-critical/5 p-8 text-center">
          <AlertOctagon className="h-8 w-8 text-critical" aria-hidden />
          <p className="text-sm font-medium text-text">This page hit an error and couldn't render.</p>
          <p className="max-w-sm text-xs text-muted">
            The rest of SHERLOCK is still usable — navigate elsewhere, or try reloading this page.
          </p>
          <Button variant="secondary" size="sm" onClick={() => this.setState({ error: null })}>
            Try again
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}
