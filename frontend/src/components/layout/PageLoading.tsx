export function PageLoading() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="flex flex-col items-center gap-2">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-accent" aria-hidden />
        <p className="font-mono text-xs text-muted">Loading…</p>
      </div>
    </div>
  )
}
