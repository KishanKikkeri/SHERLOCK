/**
 * Renders a Record<rowLabel, Record<colLabel, count>> cross-tabulation
 * (backend/intelligence/sociological_insights.py's correlation_matrix)
 * as a shaded grid — the "correlation matrix" the dashboard brief asks
 * for. Cell shade intensity is relative to the matrix's own max value,
 * not a fixed scale, so it stays legible whether the sample is 8 people
 * or 800.
 */
export function CorrelationHeatmap({
  matrix,
  rowHeader,
  colHeader,
}: {
  matrix: Record<string, Record<string, number>>
  rowHeader: string
  colHeader: string
}) {
  const rows = Object.keys(matrix)
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(matrix[r])))).sort()
  const max = Math.max(1, ...rows.flatMap((r) => Object.values(matrix[r])))

  if (rows.length === 0 || cols.length === 0) {
    return <p className="text-xs text-muted">No cross-tabulation available for this scope.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="border-b border-border p-1.5 text-left font-medium text-muted">
              {rowHeader} \ {colHeader}
            </th>
            {cols.map((c) => (
              <th key={c} className="border-b border-border p-1.5 text-center font-medium text-muted">
                {c.replaceAll('_', ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <td className="border-b border-border-subtle p-1.5 font-medium text-text">{r}</td>
              {cols.map((c) => {
                const value = matrix[r][c] ?? 0
                const intensity = value / max
                return (
                  <td
                    key={c}
                    className="border-b border-border-subtle p-1.5 text-center font-mono text-text"
                    style={{ backgroundColor: `rgba(3, 105, 161, ${intensity * 0.45})` }}
                    title={`${r} × ${c}: ${value}`}
                  >
                    {value || '—'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
