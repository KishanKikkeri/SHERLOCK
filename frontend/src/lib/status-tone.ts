import type { SessionPriority, SessionStatus } from './types'
import type { BadgeProps } from '@/components/ui/Badge'

type Tone = NonNullable<BadgeProps['tone']>

export function priorityTone(priority: SessionPriority): Tone {
  switch (priority) {
    case 'critical':
      return 'critical'
    case 'high':
      return 'warning'
    case 'medium':
      return 'info'
    case 'low':
    default:
      return 'neutral'
  }
}

export function statusTone(status: SessionStatus): Tone {
  switch (status) {
    case 'open':
      return 'positive'
    case 'reopened':
      return 'info'
    case 'closed':
      return 'neutral'
    case 'archived':
      return 'neutral'
    default:
      return 'neutral'
  }
}

export function confidenceTone(confidence: number): { tone: Tone; label: string } {
  if (confidence > 0.8) return { tone: 'positive', label: 'High confidence' }
  if (confidence >= 0.5) return { tone: 'warning', label: 'Moderate confidence' }
  return { tone: 'critical', label: 'Low confidence' }
}

export function riskBandTone(band: 'Very Low' | 'Low' | 'Moderate' | 'High' | 'Critical'): Tone {
  switch (band) {
    case 'Very Low':
    case 'Low':
      return 'positive'
    case 'Moderate':
      return 'warning'
    case 'High':
    case 'Critical':
      return 'critical'
    default:
      return 'neutral'
  }
}

export function investigationPriorityTone(
  priority: 'Routine' | 'Important' | 'Priority' | 'Urgent' | 'Critical',
): Tone {
  switch (priority) {
    case 'Routine':
      return 'neutral'
    case 'Important':
      return 'info'
    case 'Priority':
      return 'warning'
    case 'Urgent':
    case 'Critical':
      return 'critical'
    default:
      return 'neutral'
  }
}
