import {
  Info,
  Plus,
  Trash2,
  Settings,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader, EmptyState } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Tabs, TabPanel } from '@/components/ui/Tabs'
import { Table, THead, TBody, TR, TH, TD, EmptyRow } from '@/components/ui/Table'
import { Tooltip } from '@/components/ui/Tooltip'
import { Modal } from '@/components/ui/Modal'
import { Skeleton } from '@/components/ui/Skeleton'
import { useState } from 'react'

const SEMANTIC_TOKENS = [
  { name: 'background', var: '--background', usage: 'App background' },
  { name: 'surface', var: '--surface', usage: 'Cards, panels' },
  { name: 'surface-raised', var: '--surface-raised', usage: 'Hover, active' },
  { name: 'surface-sunken', var: '--surface-sunken', usage: 'Inputs, wells' },
  { name: 'border', var: '--border', usage: 'Default borders' },
  { name: 'border-strong', var: '--border-strong', usage: 'Emphasized borders' },
  { name: 'text', var: '--text', usage: 'Primary text' },
  { name: 'muted', var: '--text-muted', usage: 'Secondary text' },
  { name: 'subtle', var: '--text-subtle', usage: 'Tertiary text' },
  { name: 'accent', var: '--accent', usage: 'Primary action' },
  { name: 'ring', var: '--ring', usage: 'Focus ring' },
  { name: 'positive', var: '--positive', usage: 'Success, open' },
  { name: 'warning', var: '--warning', usage: 'Caution, high' },
  { name: 'critical', var: '--critical', usage: 'Error, critical' },
  { name: 'info', var: '--info', usage: 'Informational' },
]

const ENTITY_TOKENS = [
  { name: 'Person', var: '--entity-person' },
  { name: 'Officer', var: '--entity-officer' },
  { name: 'Organization', var: '--entity-organization' },
  { name: 'Vehicle', var: '--entity-vehicle' },
  { name: 'Weapon', var: '--entity-weapon' },
  { name: 'BankAccount', var: '--entity-bank-account' },
  { name: 'Transaction', var: '--entity-transaction' },
  { name: 'Phone', var: '--entity-phone' },
  { name: 'Location', var: '--entity-location' },
  { name: 'FIR', var: '--entity-fir' },
  { name: 'Crime', var: '--entity-crime' },
  { name: 'Property', var: '--entity-property' },
]

const TYPE_SCALE = [
  { label: '2xs', size: '0.625rem', usage: 'Labels, metadata' },
  { label: 'xs', size: '0.75rem', usage: 'Badges, secondary text' },
  { label: 'sm', size: '0.8125rem', usage: 'Body compact' },
  { label: 'base', size: '0.875rem', usage: 'Body default' },
  { label: 'lg', size: '1rem', usage: 'Emphasis' },
  { label: 'xl', size: '1.25rem', usage: 'Section headers' },
  { label: '2xl', size: '1.5rem', usage: 'Page titles' },
  { label: '3xl', size: '2rem', usage: 'Hero metrics' },
]

const SPACING_SCALE = [
  { name: '1', px: '2px' },
  { name: '2', px: '4px' },
  { name: '3', px: '8px' },
  { name: '4', px: '12px' },
  { name: '5', px: '16px' },
  { name: '6', px: '20px' },
  { name: '8', px: '24px' },
  { name: '10', px: '32px' },
  { name: '12', px: '40px' },
  { name: '16', px: '56px' },
]

function Swatch({ name, cssVar, usage }: { name: string; cssVar: string; usage: string }) {
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-10 w-10 shrink-0 rounded-md border border-border"
        style={{ background: `var(${cssVar})` }}
      />
      <div className="min-w-0">
        <p className="text-sm font-medium text-text">{name}</p>
        <p className="truncate font-mono text-xs text-muted">{cssVar}</p>
        <p className="text-xs text-subtle">{usage}</p>
      </div>
    </div>
  )
}

function EntitySwatch({ name, cssVar }: { name: string; cssVar: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-6 w-6 shrink-0 rounded-full border border-border"
        style={{ background: `var(${cssVar})` }}
      />
      <span className="text-xs text-text">{name}</span>
    </div>
  )
}

export function StyleguidePage() {
  const [tab, setTab] = useState('tokens')
  const [modalOpen, setModalOpen] = useState(false)
  const [density, setDensity] = useState<'comfortable' | 'compact'>('comfortable')

  return (
    <div data-density={density} className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Design System</h1>
        <p className="mt-1 text-sm text-muted">
          Single source of truth for SHERLOCK's visual language. Dark-mode-first,
          inspired by Linear (density), Palantir Gotham (data gravity), and
          Defender XDR (status hierarchy).
        </p>
      </div>

      <Tabs
        items={[
          { label: 'Tokens', value: 'tokens' },
          { label: 'Typography', value: 'type' },
          { label: 'Spacing', value: 'spacing' },
          { label: 'Components', value: 'components' },
          { label: 'Density', value: 'density' },
        ]}
        value={tab}
        onChange={setTab}
      />

      <TabPanel value="tokens" active={tab}>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader title="Semantic color" subtitle="Surfaces, text, status" />
            <CardBody>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {SEMANTIC_TOKENS.map((t) => (
                  <Swatch key={t.name} name={t.name} cssVar={t.var} usage={t.usage} />
                ))}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Entity color" subtitle="Graph nodes, board cards" />
            <CardBody>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {ENTITY_TOKENS.map((t) => (
                  <EntitySwatch key={t.name} name={t.name} cssVar={t.var} />
                ))}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Radius" />
            <CardBody>
              <div className="flex flex-wrap items-end gap-4">
                {[
                  { name: 'xs', val: '3px' },
                  { name: 'sm', val: '5px' },
                  { name: 'md', val: '8px' },
                  { name: 'lg', val: '12px' },
                  { name: 'full', val: '9999px' },
                ].map((r) => (
                  <div key={r.name} className="flex flex-col items-center gap-1">
                    <div
                      className="h-12 w-12 border border-border-strong bg-surface-raised"
                      style={{ borderRadius: r.val }}
                    />
                    <span className="text-xs text-muted">{r.name}</span>
                    <span className="font-mono text-xs text-subtle">{r.val}</span>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Shadow / Elevation" />
            <CardBody>
              <div className="flex flex-wrap gap-6">
                {(['sm', 'md', 'lg', 'xl'] as const).map((s) => (
                  <div key={s} className="flex flex-col items-center gap-2">
                    <div
                      className="h-16 w-16 rounded-lg border border-border bg-surface"
                      style={{ boxShadow: `var(--shadow-${s})` }}
                    />
                    <span className="text-xs text-muted">shadow-{s}</span>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>
      </TabPanel>

      <TabPanel value="type" active={tab}>
        <Card>
          <CardHeader title="Type scale" subtitle="Fira Sans (sans) + Fira Code (mono)" />
          <CardBody>
            <div className="flex flex-col gap-3">
              {TYPE_SCALE.map((t) => (
                <div
                  key={t.label}
                  className="flex items-baseline justify-between gap-4 border-b border-border-subtle pb-3"
                >
                  <div className="flex items-baseline gap-3">
                    <span className="w-10 font-mono text-xs text-muted">{t.label}</span>
                    <span style={{ fontSize: t.size }} className="font-semibold text-text">
                      The quick brown fox
                    </span>
                  </div>
                  <div className="flex items-baseline gap-3">
                    <span className="text-xs text-subtle">{t.usage}</span>
                    <span className="font-mono text-xs text-muted">{t.size}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </TabPanel>

      <TabPanel value="spacing" active={tab}>
        <Card>
          <CardHeader title="Spacing scale" subtitle="8px base system" />
          <CardBody>
            <div className="flex flex-col gap-2">
              {SPACING_SCALE.map((s) => (
                <div key={s.name} className="flex items-center gap-3">
                  <span className="w-8 font-mono text-xs text-muted">{s.name}</span>
                  <div
                    className="h-4 rounded-sm bg-accent/30"
                    style={{ width: s.px }}
                  />
                  <span className="font-mono text-xs text-subtle">{s.px}</span>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </TabPanel>

      <TabPanel value="components" active={tab}>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader title="Button" subtitle="5 variants × 5 sizes + loading" />
            <CardBody className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-2">
                <Button variant="primary">Primary</Button>
                <Button variant="secondary">Secondary</Button>
                <Button variant="ghost">Ghost</Button>
                <Button variant="outline">Outline</Button>
                <Button variant="destructive">Destructive</Button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="xs">XS</Button>
                <Button size="sm">SM</Button>
                <Button size="md">MD</Button>
                <Button size="lg">LG</Button>
                <Button size="icon" aria-label="Settings"><Settings className="h-4 w-4" /></Button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button isLoading>Loading</Button>
                <Button disabled>Disabled</Button>
                <Button variant="primary" isLoading><Plus className="h-4 w-4" /> Creating…</Button>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Badge" subtitle="5 semantic tones" />
            <CardBody className="flex flex-wrap gap-2">
              <Badge tone="neutral">Neutral</Badge>
              <Badge tone="positive">Positive</Badge>
              <Badge tone="warning">Warning</Badge>
              <Badge tone="critical">Critical</Badge>
              <Badge tone="info">Info</Badge>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Input & Select" />
            <CardBody className="flex flex-col gap-4">
              <Input label="Username" placeholder="Enter username…" />
              <Input label="With error" error="This field is required" defaultValue="bad" />
              <Select label="Role">
                <option>Administrator</option>
                <option>Supervisor</option>
                <option>Investigator</option>
              </Select>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Tooltip" subtitle="Hover or keyboard-focus to reveal" />
            <CardBody className="flex flex-wrap gap-4">
              <Tooltip content="Delete this item" side="top">
                <Button variant="ghost" size="icon" aria-label="Delete"><Trash2 className="h-4 w-4" /></Button>
              </Tooltip>
              <Tooltip content="Settings panel" side="right">
                <Button variant="ghost" size="icon" aria-label="Settings"><Settings className="h-4 w-4" /></Button>
              </Tooltip>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Modal" />
            <CardBody>
              <Button onClick={() => setModalOpen(true)}>Open modal</Button>
              <Modal
                open={modalOpen}
                onClose={() => setModalOpen(false)}
                title="Confirm action"
                description="This will permanently delete the selected evidence card."
                footer={
                  <>
                    <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
                    <Button variant="destructive" onClick={() => setModalOpen(false)}>
                      <Trash2 className="h-4 w-4" /> Delete
                    </Button>
                  </>
                }
              >
                <p className="text-sm text-muted">
                  This action cannot be undone. The card and all its links will be
                  removed from the board.
                </p>
              </Modal>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Skeleton & Empty state" />
            <CardBody className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
              <EmptyState
                icon={<Info className="h-6 w-6" />}
                title="No results"
                description="Try adjusting your filters or search query."
              />
            </CardBody>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader title="Table" />
            <CardBody>
              <Table>
                <THead>
                  <TR>
                    <TH>Session</TH>
                    <TH>Priority</TH>
                    <TH>Status</TH>
                    <TH>Updated</TH>
                  </TR>
                </THead>
                <TBody>
                  <TR>
                    <TD className="font-mono">FIR-2024-0421</TD>
                    <TD><Badge tone="critical">Critical</Badge></TD>
                    <TD><Badge tone="positive">Open</Badge></TD>
                    <TD className="text-muted">2 hours ago</TD>
                  </TR>
                  <TR>
                    <TD className="font-mono">FIR-2024-0388</TD>
                    <TD><Badge tone="warning">High</Badge></TD>
                    <TD><Badge tone="info">Reopened</Badge></TD>
                    <TD className="text-muted">1 day ago</TD>
                  </TR>
                  <EmptyRow colSpan={4}>
                    <div className="flex flex-col items-center gap-2">
                      <Info className="h-5 w-5 text-subtle" />
                      <span>No more rows</span>
                    </div>
                  </EmptyRow>
                </TBody>
              </Table>
            </CardBody>
          </Card>
        </div>
      </TabPanel>

      <TabPanel value="density" active={tab}>
        <Card>
          <CardHeader
            title="Density system"
            subtitle="Compact vs comfortable — toggle to see primitives respond"
            action={
              <div className="flex gap-1">
                <Button
                  variant={density === 'comfortable' ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => setDensity('comfortable')}
                >
                  Comfortable
                </Button>
                <Button
                  variant={density === 'compact' ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => setDensity('compact')}
                >
                  Compact
                </Button>
              </div>
            }
          />
          <CardBody>
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted">
                Density is controlled by a <code className="font-mono text-xs">data-density</code> attribute
                on a container. Primitives read CSS variables that cascade, so no prop-drilling
                is needed. Compact mode targets 1280px+ workstations with dense data; comfortable
                is the default.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm">Compact button</Button>
                <Button size="md">Default button</Button>
                <Input placeholder="Search…" className="max-w-xs" />
              </div>
            </div>
          </CardBody>
        </Card>
      </TabPanel>
    </div>
  )
}
