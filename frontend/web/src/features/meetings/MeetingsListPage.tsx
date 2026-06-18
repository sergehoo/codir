import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  endOfDay, endOfWeek, isAfter, isBefore, startOfDay, startOfMonth,
} from 'date-fns'
import { ArrowUpRight, CalendarClock, Filter, MapPin, Plus, Users, Search } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/widgets/EmptyState'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import { StatusBadge } from '@/components/widgets/StatusBadge'
import { safeFormat, toDate } from '@/utils/safeDate'

import { meetingsApi, meetingsKeys } from './api'
import type { Meeting } from '@/types'

const STATUSES = [
  { v: '', label: 'Toutes' },
  { v: 'draft', label: 'Brouillons' },
  { v: 'scheduled', label: 'Planifiées' },
  { v: 'in_progress', label: 'En cours' },
  { v: 'completed', label: 'Terminées' },
  { v: 'cancelled', label: 'Annulées' },
]

type Bucket = { key: string; label: string; items: Meeting[] }

/** Regroupe les meetings par période chronologique. */
function groupByPeriod(meetings: Meeting[]): Bucket[] {
  const now = new Date()
  const today = startOfDay(now)
  const tomorrow = endOfDay(now)
  const thisWeekEnd = endOfWeek(now, { weekStartsOn: 1 })
  const monthStart = startOfMonth(now)
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0)

  const inProgress: Meeting[] = []
  const todayBucket: Meeting[] = []
  const thisWeek: Meeting[] = []
  const thisMonth: Meeting[] = []
  const later: Meeting[] = []
  const past: Meeting[] = []

  meetings.forEach((m) => {
    // safe : si scheduled_start est null/undefined, on met le meeting dans "past"
    // (au lieu de crasher avec un Invalid Date).
    const d = toDate(m.scheduled_start) ?? new Date(0)
    if (m.status === 'in_progress') return inProgress.push(m)
    if (m.status === 'completed' || m.status === 'cancelled' || isBefore(d, today)) {
      return past.push(m)
    }
    if (isBefore(d, tomorrow)) return todayBucket.push(m)
    if (isBefore(d, thisWeekEnd)) return thisWeek.push(m)
    if (isAfter(d, monthStart) && isBefore(d, monthEnd)) return thisMonth.push(m)
    return later.push(m)
  })

  // Tri intelligent par bucket :
  // - Futures (today/week/month/later) → ASCENDANT (la prochaine d'abord)
  // - Passées + live → DESCENDANT (la plus récente d'abord)
  const tsOf = (m: Meeting) => (toDate(m.scheduled_start) ?? new Date(0)).getTime()
  const sortAsc = (a: Meeting, b: Meeting) => tsOf(a) - tsOf(b)
  const sortDesc = (a: Meeting, b: Meeting) => tsOf(b) - tsOf(a)

  inProgress.sort(sortDesc)
  todayBucket.sort(sortAsc)
  thisWeek.sort(sortAsc)
  thisMonth.sort(sortAsc)
  later.sort(sortAsc)
  past.sort(sortDesc)

  return ([
    { key: 'live',      label: 'En cours',                  items: inProgress },
    { key: 'today',     label: 'Aujourd\'hui',              items: todayBucket },
    { key: 'this_week', label: 'Cette semaine',             items: thisWeek },
    { key: 'this_month',label: 'Ce mois',                   items: thisMonth },
    { key: 'later',     label: 'Plus tard',                 items: later },
    { key: 'past',      label: 'Passées (récentes en premier)', items: past },
  ] as Bucket[]).filter((b) => b.items.length > 0)
}

export function MeetingsListPage() {
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: meetingsKeys.list({ status, search }),
    queryFn: () => meetingsApi.list({ status: status || undefined, search: search || undefined }),
  })
  const items = (Array.isArray(data) ? data : (data?.results ?? [])) as Meeting[]
  const buckets = groupByPeriod(items)

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Comité de direction"
        title="Réunions"
        description={items.length > 0 ? `${items.length} session(s) au total` : undefined}
        actions={
          <Link to="/meetings/new">
            <PremiumButton iconLeft={<Plus size={15} />}>Nouvelle réunion</PremiumButton>
          </Link>
        }
      />

      <section className="px-10 py-5 border-b border-border bg-bg-subtle/30 flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle" />
          <input
            className="input pl-9"
            placeholder="Rechercher par titre, lieu…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
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
      </section>

      <section className="px-10 py-8">
        {isLoading && <SkeletonList rows={4} />}

        {!isLoading && items.length === 0 && (
          <EmptyState
            icon={CalendarClock}
            title="Aucune réunion."
            description="Créez votre premier comité de direction pour commencer à orchestrer vos décisions."
            action={
              <Link to="/meetings/new">
                <PremiumButton iconLeft={<Plus size={15} />}>Nouvelle réunion</PremiumButton>
              </Link>
            }
          />
        )}

        {!isLoading && buckets.map((bucket) => (
          <div key={bucket.key} className="mb-10 last:mb-0 animate-fade-in-up">
            <div className="flex items-baseline gap-3 mb-4">
              <span className="divider-accent" />
              <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
                {bucket.label}
              </h2>
              <span className="chip-quiet">{bucket.items.length}</span>
            </div>
            <div className="space-y-2.5">
              {bucket.items.map((m, i) => (
                <MeetingRow key={m.id} m={m} index={i} />
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}

function MeetingRow({ m, index }: { m: Meeting; index: number }) {
  return (
    <Link
      to="/meetings/$id" params={{ id: m.id }}
      className="card p-5 block group"
    >
      <div className="flex items-start gap-5">
        <span className="text-fg-subtle font-mono text-2xs tabular pt-1.5 w-6">
          {(index + 1).toString().padStart(2, '0')}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 mb-1">
            <h3 className="text-h3 font-medium group-hover:text-copper-400 transition truncate">
              {m.title}
            </h3>
            <StatusBadge status={m.status} className="shrink-0" />
          </div>
          <div className="flex items-center gap-5 text-2xs uppercase tracking-wider text-fg-subtle flex-wrap">
            <span>{safeFormat(m.scheduled_start, "EEE d MMM · HH:mm", { fallback: 'Date non définie' })}</span>
            {m.location && (
              <span className="inline-flex items-center gap-1"><MapPin size={11} /> {m.location}</span>
            )}
            <span className="inline-flex items-center gap-1">
              <Users size={11} /> {m.participants_count ?? 0} participants
            </span>
          </div>
        </div>
        <ArrowUpRight size={16} className="text-fg-subtle group-hover:text-copper-400 transition mt-1" />
      </div>
    </Link>
  )
}
