import { ShieldCheck } from 'lucide-react'
import type { OffenderInvestigationPriority, OffenderRiskProfile } from '@/lib/types'

export function EvidencePanel({
  risk,
  priority,
}: {
  risk: OffenderRiskProfile
  priority: OffenderInvestigationPriority
}) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="mb-1.5 text-xs font-medium text-muted">Why this risk score ({risk.overall_score}/100)</p>
        <ul className="flex flex-col gap-1.5">
          {risk.because.map((line, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-text">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" aria-hidden />
              {line}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <p className="mb-1.5 text-xs font-medium text-muted">Why {priority.priority} priority</p>
        <ul className="flex flex-col gap-1.5">
          {priority.because.map((line, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-text">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" aria-hidden />
              {line}
            </li>
          ))}
        </ul>
      </div>

      <details className="rounded-md border border-border bg-surface-sunken p-3 text-xs">
        <summary className="cursor-pointer font-medium text-muted">Risk component breakdown</summary>
        <table className="mt-2 w-full">
          <tbody>
            {Object.entries(risk.components).map(([key, value]) => (
              <tr key={key}>
                <td className="py-0.5 pr-3 capitalize text-muted">{key.replace(/_/g, ' ')}</td>
                <td className="py-0.5 pr-3 text-text">{value}/100</td>
                <td className="py-0.5 text-subtle">× {Math.round(risk.weights[key] * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
