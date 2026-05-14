import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  AlertTriangle, Archive, ArrowUpRight, CheckCircle2, CheckSquare,
  ChevronDown, ChevronRight, History, Plus,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { EmptyState } from '@/components/widgets/EmptyState'
import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { PriorityBadge } from '@/components/widgets/PriorityBadge'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import { StatsBar } from '@/components/widgets/StatsBar'
import { StatusBadge } from '@/components/widgets/StatusBadge'
import type { ActionPlan, ActionTask } from '@/types'

import { AddTaskForm } from './AddTaskForm'
import { actionPlansApi, plansKeys } from './api'

const SUB_LABEL_DEFAULT = 'Sans filiale'

function groupBySubsidiary(plans: ActionPlan[]) {
  const map = new Map<string, { label: string; items: ActionPlan[] }>()
  plans.forEach((p) => {
    const key = p.subsidiary_id ?? '__none__'
    const label = p.subsidiary_name ?? SUB_LABEL_DEFAULT
    if (!map.has(key)) map.set(key, { label, items: [] })
    map.get(key)!.items.push(p)
  })
  return Array.from(map.values()).sort((a, b) => {
    if (a.label === SUB_LABEL_DEFAULT) return 1
    if (b.label === SUB_LABEL_DEFAULT) return -1
    return a.label.localeCompare(b.label)
  })
}

const ACTIVE_STATUSES = new Set(['open', 'in_progress', 'blocked'])
const ARCHIVED_STATUSES = new Set(['completed', 'cancelled'])

export function ActionPlansListPage() {
  const { data, isLoading } = useQuery({ queryKey: plansKeys.list(), queryFn: () => actionPlansApi.list() })
  const allItems = (Array.isArray(data) ? data : (data?.results ?? [])) as ActionPlan[]
  const { data: stats } = useQuery({ queryKey: plansKeys.stats(), queryFn: () => actionPlansApi.stats() })

  // Séparation actif / historique
  const active = allItems.filter((p) => ACTIVE_STATUSES.has(p.status) && p.progress_percent < 100)
  const archived = allItems.filter((p) => ARCHIVED_STATUSES.has(p.status) || p.progress_percent >= 100)

  const activeGroups = groupBySubsidiary(active)
  const showActiveGrouping = activeGroups.length > 1

  const [showHistory, setShowHistory] = useState(false)

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Exécution"
        title="Plans d'action"
        description={
          active.length > 0
            ? `${active.length} plan(s) en cours · ${archived.length} archivé(s)`
            : `${archived.length} plan(s) archivé(s)`
        }
      />

      <section className="px-10 pt-6 -mt-2">
        <StatsBar items={[
          { label: 'En cours',     value: active.length,                              tone: 'copper' },
          { label: 'Avancement',   value: `${Math.round(stats?.avg_progress ?? 0)}%`, tone: 'info' },
          { label: 'Achevés',      value: stats?.completed ?? archived.length,        tone: 'success' },
          { label: 'Bloqués',      value: stats?.blocked ?? 0,                        tone: 'warning' },
        ]} />
      </section>

      <section className="px-10 py-8">
        {isLoading && <SkeletonList rows={4} />}

        {!isLoading && active.length === 0 && archived.length === 0 && (
          <EmptyState
            icon={CheckSquare}
            title="Aucun plan d'action."
            description="Convertissez une décision validée pour générer son plan d'exécution."
          />
        )}

        {/* ─── Actifs (accordéons) ──────────────────────────── */}
        {!isLoading && active.length > 0 && (
          <>
            {!showActiveGrouping && (
              <div className="space-y-3">
                {active.map((p, i) => <PlanAccordion key={p.id} p={p} idx={i} />)}
              </div>
            )}
            {showActiveGrouping && activeGroups.map((g) => (
              <div key={g.label} className="mb-10 last:mb-0 animate-fade-in-up">
                <div className="flex items-center gap-3 mb-4">
                  <span className="divider-accent" />
                  <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">{g.label}</h2>
                  <span className="chip-quiet">{g.items.length}</span>
                </div>
                <div className="space-y-3">
                  {g.items.map((p, i) => <PlanAccordion key={p.id} p={p} idx={i} />)}
                </div>
              </div>
            ))}
          </>
        )}

        {!isLoading && active.length === 0 && archived.length > 0 && (
          <div className="card p-8 text-center text-fg-muted text-sm mb-6">
            <CheckCircle2 size={24} className="mx-auto text-success mb-2" />
            Tous les plans d'action sont clôturés. Bravo.
          </div>
        )}

        {/* ─── Historique (collapsible) ──────────────────────── */}
        {!isLoading && archived.length > 0 && (
          <div className="mt-10">
            <button
              onClick={() => setShowHistory((v) => !v)}
              className="w-full flex items-center gap-3 px-1 py-3 border-t border-border text-left group"
            >
              {showHistory
                ? <ChevronDown size={16} className="text-fg-muted" />
                : <ChevronRight size={16} className="text-fg-muted" />}
              <History size={14} className="text-fg-subtle" />
              <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold flex-1">
                Historique — plans clôturés
              </span>
              <span className="chip-quiet">{archived.length}</span>
            </button>

            {showHistory && (
              <div className="mt-4 space-y-2 animate-fade-in-up">
                {archived.map((p, i) => (
                  <PlanArchivedRow key={p.id} p={p} idx={i} />
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

// ─── Accordéon plan + tâches ─────────────────────────────────

function PlanAccordion({ p, idx }: { p: ActionPlan; idx: number }) {
  const [open, setOpen] = useState(false)
  const [showAdd, setShowAdd] = useState(false)

  // Lazy load tasks à l'ouverture
  const { data: tasks, isLoading } = useQuery({
    queryKey: plansKeys.tasks(p.id),
    queryFn: () => actionPlansApi.listTasks(p.id),
    enabled: open,
  })

  const overdue = (tasks ?? []).filter((t) => t.is_overdue).length
  const canAdd = p.can_add_tasks !== false  // optimiste si non fourni

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left p-5 hover:bg-fg/[0.02] transition flex items-start gap-5"
      >
        <span className="text-fg-subtle font-mono text-2xs tabular pt-1.5 w-6">
          {(idx + 1).toString().padStart(2, '0')}
        </span>

        {open
          ? <ChevronDown size={16} className="text-copper-400 mt-1 shrink-0" />
          : <ChevronRight size={16} className="text-fg-subtle mt-1 shrink-0" />}

        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 mb-1 flex-wrap">
            <h3 className="text-h3 font-medium truncate">{p.title}</h3>
            <StatusBadge status={p.status} className="shrink-0" />
            {overdue > 0 && (
              <span className="chip-danger inline-flex items-center gap-1">
                <AlertTriangle size={10} /> {overdue} en retard
              </span>
            )}
          </div>
          <div className="flex items-center gap-5 text-2xs uppercase tracking-wider text-fg-subtle flex-wrap">
            {p.owner_detail && <span>📌 {p.owner_detail.full_name}</span>}
            {p.decision_ref && <span className="font-mono">{p.decision_ref}</span>}
            {p.subsidiary_name && <span className="text-copper-400/80">{p.subsidiary_name}</span>}
            {p.target_end_date && (
              <span>Cible : {format(new Date(p.target_end_date), 'd MMM yyyy', { locale: fr })}</span>
            )}
            <span>{p.tasks_count} tâche(s)</span>
          </div>
          <div className="mt-3 flex items-center gap-3 max-w-md">
            <div className="flex-1 h-1 bg-fg/[0.05] rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-copper-gradient transition-all duration-700"
                   style={{ width: `${p.progress_percent}%` }} />
            </div>
            <span className="text-2xs tabular text-fg-muted w-9 text-right">{p.progress_percent}%</span>
          </div>
        </div>

        <Link
          to="/action-plans/$id" params={{ id: p.id }}
          onClick={(e) => e.stopPropagation()}
          className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold mt-1 inline-flex items-center gap-1 shrink-0"
        >
          Détail <ArrowUpRight size={11} />
        </Link>
      </button>

      {/* Tâches en accordéon */}
      {open && (
        <div className="border-t border-border bg-bg-subtle/30 px-5 py-4 animate-fade-in-up">
          <div className="flex items-center justify-between gap-3 mb-3">
            <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
              Tâches du plan
              {tasks && tasks.length > 0 && (
                <span className="ml-2 chip-quiet">{tasks.length}</span>
              )}
            </span>
            {canAdd && (
              <PremiumButton
                size="sm" variant="secondary"
                iconLeft={<Plus size={12} />}
                onClick={(e) => { e.stopPropagation(); setShowAdd(true) }}
              >
                Nouvelle tâche
              </PremiumButton>
            )}
          </div>

          {isLoading && <p className="text-fg-subtle text-sm py-2">Chargement des tâches…</p>}
          {!isLoading && (tasks?.length ?? 0) === 0 && (
            <div className="py-4 text-center">
              <p className="text-fg-subtle text-sm mb-2">Aucune tâche pour ce plan.</p>
              {canAdd && (
                <button
                  onClick={(e) => { e.stopPropagation(); setShowAdd(true) }}
                  className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold"
                >
                  + Créer la première tâche
                </button>
              )}
            </div>
          )}
          {!isLoading && (tasks?.length ?? 0) > 0 && (
            <div className="space-y-1.5">
              {tasks!.map((t, i) => <TaskInlineRow key={t.id} t={t} idx={i} planId={p.id} />)}
            </div>
          )}
        </div>
      )}

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title={`Nouvelle tâche — ${p.title}`}>
        <AddTaskForm
          planId={p.id}
          onCreated={() => setShowAdd(false)}
          onCancel={() => setShowAdd(false)}
        />
      </Modal>
    </div>
  )
}

function TaskInlineRow({ t, idx, planId }: { t: ActionTask; idx: number; planId: string }) {
  const qc = useQueryClient()
  const complete = useMutation({
    mutationFn: () => actionPlansApi.completeTask(t.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: plansKeys.tasks(planId) })
      qc.invalidateQueries({ queryKey: plansKeys.list() })
      qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', t.id] })
      toast.success('Tâche clôturée')
    },
  })

  return (
    <div className={`flex items-center gap-3 px-3 py-2.5 rounded transition group ${
      t.is_overdue ? 'bg-danger/5 border border-danger/20' : 'bg-bg-elevated hover:bg-fg/[0.04]'
    }`}>
      <span className="text-fg-subtle font-mono text-2xs tabular w-6 shrink-0">
        {(idx + 1).toString().padStart(2, '0')}
      </span>

      <Link
        to="/tasks/$id" params={{ id: t.id }}
        className="flex-1 min-w-0 cursor-pointer"
      >
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium truncate group-hover:text-copper-400 transition">{t.title}</span>
          <PriorityBadge priority={t.priority} />
          {t.is_overdue && (
            <span className="text-2xs text-danger uppercase tracking-wider flex items-center gap-1">
              <AlertTriangle size={10} /> Retard
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 text-2xs uppercase tracking-wider text-fg-subtle">
          {t.assignee_detail && <span>→ {t.assignee_detail.full_name}</span>}
          {t.due_date && <span>⏰ {format(new Date(t.due_date), 'dd/MM/yyyy')}</span>}
          <span className="tabular">{t.progress_percent}%</span>
        </div>
      </Link>

      <StatusBadge status={t.status} className="shrink-0" />
      {t.status !== 'done' && t.status !== 'cancelled' && (
        <button
          onClick={(e) => { e.stopPropagation(); complete.mutate() }}
          disabled={complete.isPending}
          className="text-2xs text-copper-400 hover:underline uppercase tracking-wider font-semibold shrink-0"
        >
          Clôturer
        </button>
      )}
    </div>
  )
}

// ─── Historique (compact) ────────────────────────────────────

function PlanArchivedRow({ p, idx }: { p: ActionPlan; idx: number }) {
  return (
    <Link to="/action-plans/$id" params={{ id: p.id }}
          className="block px-4 py-3 rounded-md border border-border/60 bg-bg-subtle/40 hover:bg-fg/[0.03] transition group">
      <div className="flex items-center gap-4">
        <span className="text-fg-subtle font-mono text-2xs tabular w-6 shrink-0">
          {(idx + 1).toString().padStart(2, '0')}
        </span>
        <Archive size={13} className="text-fg-subtle shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3">
            <span className="text-sm font-medium group-hover:text-copper-400 transition truncate">
              {p.title}
            </span>
            <StatusBadge status={p.status} className="shrink-0" />
          </div>
          <div className="flex items-center gap-4 text-2xs uppercase tracking-wider text-fg-subtle mt-0.5 flex-wrap">
            {p.owner_detail && <span>{p.owner_detail.full_name}</span>}
            {p.decision_ref && <span className="font-mono">{p.decision_ref}</span>}
            {p.actual_end_date && (
              <span>Clôturé : {format(new Date(p.actual_end_date), 'd MMM yyyy', { locale: fr })}</span>
            )}
            <span>{p.tasks_count} tâche(s)</span>
          </div>
        </div>
        <span className="text-2xs tabular text-success font-semibold w-12 text-right">
          {p.progress_percent}%
        </span>
        <ArrowUpRight size={14} className="text-fg-subtle group-hover:text-copper-400 transition" />
      </div>
    </Link>
  )
}
