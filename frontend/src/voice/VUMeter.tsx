export function VUMeter({ level, className }: { level: number; className?: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, level)) * 100)
  return (
    <div
      className={className}
      role="meter"
      aria-label="Microphone level"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-raised">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-75 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
