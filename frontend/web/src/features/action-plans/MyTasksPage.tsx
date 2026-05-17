import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { AlertTriangle, CheckSquare } from 'lucide-react'

import { EmptyState } from '@/components/widgets/EmptyState'
import { PriorityBadge } from '@/components/widgets/PriorityBadge'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import { StatsBar } from '@/components/widgets/StatsBar'
import { StatusBadge } from '@/components/widgets/StatusBadge'
import type { ActionTask } from '@/types'

import { actionPlansApi, plansKeys } from './api'
import { DelegateButton } from './DelegateTaskModal'

const SUB_LABEL_DEFAULT = 'Sans filiale'

function groupBySubsidiary(tasks: ActionTask[]) {
  const map = new Map<string, { label: string; items: ActionTask[] }>()
  tasks.forEach((t) => {
    const key = t.subsidiary_id ?? '__none__'
    const label = t.subsidiary_name ?? SUB_LABEL_DEFAULT
    if (!map.has(key)) map.set(key, { label, items: [] })
    map.get(key)!.items.push(t)
  })
  return Array.from(map.values())
}

export function MyTasksPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: plansKeys.myTasks(),
    queryFn: () => actionPlansApi.myTasks(),
  })
  const tasks = (Array.isArray(data) ? data : (data?.results ?? [])) as ActionTask[]

  const complete = useMutation({
    mutationFn: (id: string) => actionPlansApi.completeTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: plansKeys.myTasks() }),
  })

  const overdue = tasks.filter((t) => t.is_overdue)
  const today = tasks.filter((t) => !t.is_overdue)
  const byPriority = (p: string) => tasks.filter((t) => t.priority === p).length

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Personnel"
        title="Mes tâches"
        description={`${tasks.length} tâche(s) en cours${overdue.length ? ` · ${overdue.length} en retard` : ''}`}
      />

      <section className="px-10 pt-6 -mt-2">
        <StatsBar items={[
          { label: 'En cours',  value: tasks.length, tone: 'copper' },
          { label: 'En retard', value: overdue.length, tone: 'danger' },
          { label: 'Critiques', value: byPriority('critical'), tone: 'warning' },
          { label: 'Élevées',   value: byPriority('high'),     tone: 'info' },
        ]} />
      </section>

      <section className="px-10 py-8 space-y-10">
        {isLoading && <SkeletonList rows={4} />}

        {!isLoading && tasks.length === 0 && (
          <EmptyState
            icon={CheckSquare}
            title="Boîte vide."
            description="Toutes vos tâches sont à jour. Bien joué."
          />
        )}

        {overdue.length > 0 && (
          <TaskGroup
            label="En retard"
            tone="danger"
            tasks={overdue}
            onComplete={(id) => complete.mutate(id)}
          />
        )}

        {today.length > 0 && (
          <TaskGroupBySubsidiary
            label="À traiter"
            tasks={today}
            onComplete={(id) => complete.mutate(id)}
          />
        )}
      </section>
    </div>
  )
}

function TaskGroup({
  label, tone = 'copper', tasks, onComplete,
}: { label: string; tone?: 'copper' | 'danger'; tasks: ActionTask[]; onComplete: (id: string) => void }) {
  return (
    <div className="animate-fade-in-up">
      <div className="flex items-center gap-3 mb-4">
        <span className={`divider-accent ${tone === 'danger' ? '!bg-danger' : ''}`} />
        <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">{label}</h2>
        <span className="chip-quiet">{tasks.length}</span>
      </div>
      <div className="space-y-2">
        {tasks.map((t, i) => <TaskRow key={t.id} t={t} idx={i} onComplete={onComplete} />)}
      </div>
    </div>
  )
}

function TaskGroupBySubsidiary({
  label, tasks, onComplete,
}: { label: string; tasks: ActionTask[]; onComplete: (id: string) => void }) {
  const groups = groupBySubsidiary(tasks)
  if (groups.length <= 1) {
    return <TaskGroup label={label} tasks={tasks} onComplete={onComplete} />
  }
  return (
    <div className="animate-fade-in-up">
      <div className="flex items-center gap-3 mb-5">
        <span className="divider-accent" />
        <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">{label}</h2>
      </div>
      <div className="space-y-6">
        {groups.map((g) => (
          <div key={g.label}>
            <div className="text-2xs uppercase tracking-[0.2em] text-copper-400 font-bold mb-3 flex items-center gap-2">
              <span className="inline-block w-3 h-px bg-copper-500" />
              {g.label}
              <span className="chip-quiet ml-2">{g.items.length}</span>
            </div>
            <div className="space-y-2">
              {g.items.map((t, i) => (
                <TaskRow key={t.id} t={t} idx={i} onComplete={onComplete} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function TaskRow({
  t, idx, onComplete,
}: { t: ActionTask; idx: number; onComplete: (id: string) => void }) {
  return (
    <div className="card p-4 flex items-center gap-5 hover:border-border-strong transition">
      <span className="text-fg-subtle font-mono text-2xs tabular w-6">
        {(idx + 1).toString().padStart(2, '0')}
      </span>
      <Link to="/tasks/$id" params={{ id: t.id }} className="flex-1 min-w-0 group">
        <div className="font-medium text-sm leading-tight group-hover:text-copper-400 transition">{t.title}</div>
        <div className="flex items-center gap-3 text-2xs uppercase tracking-wider text-fg-subtle mt-1.5 flex-wrap">
          <span>Plan : {t.action_plan_title || '—'}</span>
          {t.due_date && <span>· {format(new Date(t.due_date), 'dd/MM/yyyy')}</span>}
          {t.is_overdue && (
            <span className="text-danger inline-flex items-center gap-1">
              <AlertTriangle size={10} /> Retard
            </span>
          )}
        </div>
      </Link>
      <div className="flex-1 max-w-[140px]">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1 bg-fg/[0.05] rounded-full overflow-hidden">
            <div className="h-full bg-copper-gradient" style={{ width: `${t.progress_percent}%` }} />
          </div>
          <span className="text-2xs tabular text-fg-muted w-9 text-right">{t.progress_percent}%</span>
        </div>
      </div>
      <PriorityBadge priority={t.priority} />
      <StatusBadge status={t.status} />
      <DelegateButton task={t} />
      <button
        onClick={() => onComplete(t.id)}
        disabled={(t.progress_percent ?? 0) < 100}
        title={
          (t.progress_percent ?? 0) < 100
            ? `La tâche doit être à 100% (actuellement : ${t.progress_percent ?? 0}%)`
            : 'Archiver la tâche'
        }
        className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed"
      >
        Archiver
      </button>
    </div>
  )
}
