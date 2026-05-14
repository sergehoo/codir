import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { ArrowUpRight, Filter, Lock, Scale } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/widgets/EmptyState'
import { PriorityBadge } from '@/components/widgets/PriorityBadge'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import { StatsBar } from '@/components/widgets/StatsBar'
import { StatusBadge } from '@/components/widgets/StatusBadge'

import { decisionsApi, decisionsKeys } from './api'

const STATUSES = [
  { v: '', label: 'Toutes' },
  { v: 'proposed', label: 'Proposées' },
  { v: 'approved', label: 'Validées' },
  { v: 'in_progress', label: 'En exécution' },
  { v: 'completed', label: 'Réalisées' },
  { v: 'postponed', label: 'Reportées' },
  { v: 'cancelled', label: 'Annulées' },
]

const PRIORITIES = [
  { v: '', label: 'Toutes' },
  { v: 'critical', label: 'Critique' },
  { v: 'high', label: 'Élevée' },
  { v: 'medium', label: 'Moyenne' },
  { v: 'low', label: 'Faible' },
]

export function DecisionsListPage() {
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: decisionsKeys.list({ status, priority }),
    queryFn: () => decisionsApi.list({ status: status || undefined, priority: priority || undefined }),
  })
  const items = Array.isArray(data) ? data : (data?.results ?? [])

  const { data: stats } = useQuery({
    queryKey: [...decisionsKeys.all, 'stats'],
    queryFn: () => decisionsApi.stats(),
  })

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Gouvernance"
        title="Décisions"
        description={items.length > 0 ? `${items.length} décision(s)` : undefined}
      />

      <section className="px-10 pt-6 -mt-2">
        <StatsBar items={[
          { label: 'Total',         value: stats?.total ?? items.length, tone: 'copper' },
          { label: 'À valider',     value: stats?.pending ?? 0,          tone: 'info' },
          { label: 'Validées',      value: stats?.approved ?? 0,         tone: 'success' },
          { label: 'En retard',     value: stats?.overdue ?? 0,          tone: 'danger' },
          { label: 'Confidentielles', value: stats?.confidential ?? 0,   tone: 'warning' },
        ]} />
      </section>

      <section className="px-10 py-5 border-b border-border bg-bg-subtle/20 flex items-center gap-3 flex-wrap">
        <Filter size={14} className="text-fg-subtle" />
        <div className="flex gap-1 flex-wrap">
          {STATUSES.map((s) => (
            <button
              key={s.v} onClick={() => setStatus(s.v)}
              className={`text-2xs uppercase tracking-wider px-3 py-1.5 rounded-md transition font-semibold ${
                status === s.v
                  ? 'bg-copper-500/15 text-copper-400 border border-copper-500/30'
                  : 'text-fg-muted border border-border hover:border-copper-500/30'
              }`}
            >{s.label}</button>
          ))}
        </div>
        <span className="text-fg-subtle text-2xs uppercase tracking-wider mx-2">·</span>
        <div className="flex gap-1 flex-wrap">
          {PRIORITIES.map((p) => (
            <button
              key={p.v} onClick={() => setPriority(p.v)}
              className={`text-2xs uppercase tracking-wider px-3 py-1.5 rounded-md transition font-semibold ${
                priority === p.v
                  ? 'bg-copper-500/15 text-copper-400 border border-copper-500/30'
                  : 'text-fg-muted border border-border hover:border-copper-500/30'
              }`}
            >{p.label}</button>
          ))}
        </div>
      </section>

      <section className="px-10 py-8">
        {isLoading && <SkeletonList rows={4} />}

        {!isLoading && items.length === 0 && (
          <EmptyState
            icon={Scale}
            title="Aucune décision."
            description="Créez-en depuis le panneau Décisions d'une réunion."
          />
        )}

        <div className="space-y-3">
          {items.map((d, i) => (
            <Link key={d.id} to="/decisions/$id" params={{ id: d.id }}
                  className="card p-5 block group">
              <div className="flex items-start gap-5">
                <span className="text-fg-subtle font-mono text-2xs tabular pt-1.5 w-6">
                  {(i + 1).toString().padStart(2, '0')}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="text-2xs font-mono text-fg-subtle uppercase tracking-wider">{d.ref}</span>
                    {d.is_confidential && (
                      <span className="inline-flex items-center text-2xs text-warning">
                        <Lock size={10} /> confidentielle
                      </span>
                    )}
                    <PriorityBadge priority={d.priority} />
                    <StatusBadge status={d.status} className="ml-auto" />
                  </div>
                  <h3 className="text-h3 font-medium group-hover:text-copper-400 transition leading-snug">{d.title}</h3>
                  <div className="flex items-center gap-5 text-2xs uppercase tracking-wider text-fg-subtle mt-2">
                    {d.responsible_detail && <span>📌 {d.responsible_detail.full_name}</span>}
                    {d.deadline && (
                      <span>⏰ {format(new Date(d.deadline), 'd MMM yyyy', { locale: fr })}</span>
                    )}
                  </div>
                </div>
                <ArrowUpRight size={16} className="text-fg-subtle group-hover:text-copper-400 transition mt-1" />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
