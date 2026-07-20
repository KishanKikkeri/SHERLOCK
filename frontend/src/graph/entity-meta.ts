import {
  User,
  Shield,
  Building2,
  Car,
  Crosshair,
  Landmark,
  ArrowLeftRight,
  Phone,
  Gavel,
  MapPin,
  FileText,
  TriangleAlert,
  Package,
  UserX,
  UserMinus,
  Eye,
  type LucideIcon,
} from 'lucide-react'
import type { GraphEdgeType, GraphNodeType } from '@/lib/types'

interface EntityMeta {
  label: string
  /** Tailwind class name suffix, e.g. "entity-person" -> `fill-entity-person`. */
  colorVar: string
  /** Raw hex, for contexts that need it outside Tailwind (D3 doesn't read CSS vars for physics, only paint). */
  hex: string
  icon: LucideIcon
}

// The 16 real graph node types (backend/graph/schema.py NODE_LABELS).
// This is the *only* place entity colors/icons are defined — GraphView,
// GraphLegend, and GraphControls all read from here. See
// docs/stage-f/01-DESIGN-SYSTEM.md for the color rationale.
export const ENTITY_META: Record<GraphNodeType, EntityMeta> = {
  Person: { label: 'Person', colorVar: 'entity-person', hex: '#38BDF8', icon: User },
  Officer: { label: 'Officer', colorVar: 'entity-officer', hex: '#22D3EE', icon: Shield },
  Organization: { label: 'Organization', colorVar: 'entity-organization', hex: '#A78BFA', icon: Building2 },
  Vehicle: { label: 'Vehicle', colorVar: 'entity-vehicle', hex: '#FB923C', icon: Car },
  Weapon: { label: 'Weapon', colorVar: 'entity-weapon', hex: '#F87171', icon: Crosshair },
  BankAccount: { label: 'Bank account', colorVar: 'entity-bank-account', hex: '#34D399', icon: Landmark },
  Transaction: { label: 'Transaction', colorVar: 'entity-transaction', hex: '#10B981', icon: ArrowLeftRight },
  Phone: { label: 'Phone', colorVar: 'entity-phone', hex: '#F472B6', icon: Phone },
  Court: { label: 'Court', colorVar: 'entity-court', hex: '#94A3B8', icon: Gavel },
  Location: { label: 'Location', colorVar: 'entity-location', hex: '#2DD4BF', icon: MapPin },
  FIR: { label: 'FIR', colorVar: 'entity-fir', hex: '#C2410C', icon: FileText },
  Crime: { label: 'Crime', colorVar: 'entity-crime', hex: '#EF4444', icon: TriangleAlert },
  Property: { label: 'Property', colorVar: 'entity-property', hex: '#FACC15', icon: Package },
  Accused: { label: 'Accused', colorVar: 'entity-accused', hex: '#D946EF', icon: UserX },
  Victim: { label: 'Victim', colorVar: 'entity-victim', hex: '#84CC16', icon: UserMinus },
  Witness: { label: 'Witness', colorVar: 'entity-witness', hex: '#60A5FA', icon: Eye },
}

export const ALL_NODE_TYPES = Object.keys(ENTITY_META) as GraphNodeType[]

// Not a full hand-authored table — see 02-API-CONTRACTS.md: derive from
// SNAKE_CASE unless a specific one reads badly enough to override here.
const EDGE_LABEL_OVERRIDES: Partial<Record<GraphEdgeType, string>> = {
  PERSON_LINKED_TO_PERSON: 'linked to (same crime)',
  PERSON_ASSOCIATED_WITH: 'associated with',
}

export function edgeLabel(type: GraphEdgeType): string {
  if (EDGE_LABEL_OVERRIDES[type]) return EDGE_LABEL_OVERRIDES[type]!
  const words = type.toLowerCase().replaceAll('_', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}
