import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  AlertTriangle, Archive, ArrowUpRight, CheckCircle2, CheckSquare,
  ChevronDown, ChevronRight, Loader2, Pencil, Plus, Presentation, Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { apiClient } from '@/api/client'
import { EmptyState } from '@/components/widgets/EmptyState'
import { HealthBadge } from '@/components/widgets/HealthBadge'
import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { PriorityBadge } from '@/components/widgets/PriorityBadge'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import { StatsBar } from '@/components/widgets/StatsBar'
import { StatusBadge } from '@/components/widgets/StatusBadge'
import type { ActionPlan, ActionTask } from '@/types'

import { AddTaskForm } from './AddTaskForm'
import { LiveCodirMode } from './LiveCodirMode'
import { actionPlansApi, plansKeys } from './api'

const SUB_LABEL_DEFAULT = 'Sans filiale'
const DIR_LABEL_DEFAULT = 'Sans direction'

/**
 * Hiérarchie Filiale → Direction → Plans d'action.
 * Renvoie un tableau de groupes-filiale, chacun contenant des sous-groupes
 * direction triés.
 */
function groupBySubsidiaryAndDirection(plans: ActionPlan[]) {
  const subMap = new Map<
    string,
    {
      label: string
      directions: Map<string, { label: string; items: ActionPlan[] }>
    }
  >()

  plans.forEach((p) => {
    const subKey = p.subsidiary_id ?? '__none__'
    const subLabel = p.subsidiary_name ?? SUB_LABEL_DEFAULT
    if (!subMap.has(subKey)) {
      subMap.set(subKey, { label: subLabel, directions: new Map() })
    }
    const sub = subMap.get(subKey)!

    const dirKey = p.direction_id ?? '__none__'
    const dirLabel = p.direction_name ?? DIR_LABEL_DEFAULT
    if (!sub.directions.has(dirKey)) {
      sub.directions.set(dirKey, { label: dirLabel, items: [] })
    }
    sub.directions.get(dirKey)!.items.push(p)
  })

  // Tri : filiales alpha avec "Sans filiale" en dernier ; idem pour les directions
  const sortGroups = <T extends { label: string }>(arr: T[], defaultLabel: string) =>
    arr.sort((a, b) => {
      if (a.label === defaultLabel) return 1
      if (b.label === defaultLabel) return -1
      return a.label.localeCompare(b.label)
    })

  return sortGroups(
    Array.from(subMap.values()).map((s) => ({
      label: s.label,
      directions: sortGroups(Array.from(s.directions.values()), DIR_LABEL_DEFAULT),
      totalPlans: Array.from(s.directions.values()).reduce(
        (acc, d) => acc + d.items.length,
        0,
      ),
    })),
    SUB_LABEL_DEFAULT,
  )
}

const ACTIVE_STATUSES = new Set(['open', 'in_progress', 'blocked'])

/**
 * Un plan est ARCHIVÉ uniquement s'il est explicitement terminé (status=completed)
 * ET à 100% de progression. Un plan annulé apparaît à part (non archivé).
 * Un plan à 100% mais status != completed reste en actif tant que l'archivage
 * formel n'est pas fait (pour cohérence avec la règle des tâches).
 */
function isPlanArchived(p: ActionPlan): boolean {
  return p.status === 'completed' && (p.progress_percent ?? 0) >= 100
}

export function ActionPlansListPage() {
  const { data, isLoading } = useQuery({ queryKey: plansKeys.list(), queryFn: () => actionPlansApi.list() })
  const allItems = (Array.isArray(data) ? data : (data?.results ?? [])) as ActionPlan[]
  const { data: stats } = useQuery({ queryKey: plansKeys.stats(), queryFn: () => actionPlansApi.stats() })

  // Séparation actif / archives
  // - Actif : statut open/in_progress/blocked ET pas encore à 100%
  // - Archives : strictement status=completed ET progress=100%
  const active = allItems.filter(
    (p) => ACTIVE_STATUSES.has(p.status) && (p.progress_percent ?? 0) < 100,
  )
  const archived = allItems.filter(isPlanArchived)

  // Hiérarchie Filiale → Direction → Plans d'action
  const activeGroups = groupBySubsidiaryAndDirection(active)

  const [showHistory, setShowHistory] = useState(false)
  const [liveMode, setLiveMode] = useState(false)
  const [newPlanOpen, setNewPlanOpen] = useState(false)

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Exécution"
        title="Projets / Dossiers"
        description={
          active.length > 0
            ? `${active.length} Dossier(s) en cours · ${archived.length} archivé(s)`
            : `${archived.length} Dossier(s) archivé(s)`
        }
        actions={
          <div className="flex items-center gap-2">
            <PremiumButton
              onClick={() => setNewPlanOpen(true)}
              iconLeft={<Plus size={14} />}
            >
              Nouveau dossier
            </PremiumButton>
            <button
              type="button"
              onClick={() => setLiveMode(true)}
              className="px-4 py-2 rounded-md bg-bg-elevated border border-border hover:border-copper-500/30 text-sm font-semibold flex items-center gap-2"
            >
              <Presentation size={16} />
              Live CODIR
            </button>
          </div>
        }
      />

      <NewActionPlanModal
        open={newPlanOpen}
        onClose={() => setNewPlanOpen(false)}
      />

      {liveMode && <LiveCodirMode onClose={() => setLiveMode(false)} />}

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

        {/* ─── Actifs : Filiale → Direction → Plans (hiérarchie) ──── */}
        {!isLoading && active.length > 0 && (
          <>
            {activeGroups.map((subGroup) => (
              <section key={subGroup.label} className="mb-12 last:mb-0 animate-fade-in-up">
                {/* En-tête Filiale */}
                <header className="flex items-center gap-3 mb-5 pb-2 border-b border-copper-500/30">
                  <span className="w-1 h-6 bg-copper-500 rounded-full" />
                  <h2 className="serif text-h2 font-semibold">{subGroup.label}</h2>
                  <span className="chip-copper">
                    {subGroup.totalPlans} dossier{subGroup.totalPlans > 1 ? 's' : ''}
                  </span>
                </header>

                {/* Sous-groupes Direction */}
                {subGroup.directions.map((dirGroup) => (
                  <div key={dirGroup.label} className="mb-6 last:mb-0">
                    <div className="flex items-center gap-3 mb-3 ml-1">
                      <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
                        {dirGroup.label}
                      </span>
                      <span className="flex-1 h-px bg-border" />
                      <span className="text-2xs text-fg-subtle">
                        {dirGroup.items.length}
                      </span>
                    </div>
                    <div className="space-y-3 ml-3">
                      {dirGroup.items.map((p, i) => (
                        <PlanAccordion key={p.id} p={p} idx={i} />
                      ))}
                    </div>
                  </div>
                ))}
              </section>
            ))}
          </>
        )}

        {!isLoading && active.length === 0 && archived.length > 0 && (
          <div className="card p-8 text-center text-fg-muted text-sm mb-6">
            <CheckCircle2 size={24} className="mx-auto text-success mb-2" />
            Tous les plans d'action sont clôturés. Bravo.
          </div>
        )}

        {/* ─── Archives (collapsible) ──────────────────────── */}
        {!isLoading && archived.length > 0 && (
          <div className="mt-10">
            <button
              onClick={() => setShowHistory((v) => !v)}
              className="w-full flex items-center gap-3 px-1 py-3 border-t border-border text-left group"
            >
              {showHistory
                ? <ChevronDown size={16} className="text-fg-muted" />
                : <ChevronRight size={16} className="text-fg-muted" />}
              <Archive size={14} className="text-fg-subtle" />
              <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold flex-1">
                Archives — plans terminés à 100%
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
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [showEdit, setShowEdit] = useState(false)

  // Lazy load tasks à l'ouverture
  const { data: tasks, isLoading } = useQuery({
    queryKey: plansKeys.tasks(p.id),
    queryFn: () => actionPlansApi.listTasks(p.id),
    enabled: open,
  })

  const overdue = (tasks ?? []).filter((t) => t.is_overdue).length
  const canAdd = p.can_add_tasks !== false  // optimiste si non fourni
  const canModify = p.can_modify === true   // strict : seulement si explicitement true

  const deletePlanMut = useMutation({
    mutationFn: () => apiClient.delete(`/action-plans/${p.id}/`),
    onSuccess: () => {
      toast.success(`Plan "${p.title}" supprimé`)
      qc.invalidateQueries({ queryKey: plansKeys.all })
    },
    onError: (e: any) => {
      toast.error(e?.response?.data?.detail || 'Suppression impossible')
    },
  })

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
            <HealthBadge
              score={(p as any).health_score}
              label={(p as any).health_label}
              reasons={(p as any).health_reasons}
              variant="chip"
              className="shrink-0"
            />
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

        <div className="flex items-center gap-2 mt-1 shrink-0">
          {canModify && (
            <>
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => { e.stopPropagation(); setShowEdit(true) }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    e.stopPropagation()
                    setShowEdit(true)
                  }
                }}
                className="cursor-pointer p-1.5 rounded-md text-fg-muted hover:text-copper-400 hover:bg-copper-500/10 transition"
                title="Modifier ce plan d'action"
                aria-label="Modifier"
              >
                <Pencil size={13} />
              </span>
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm(`Supprimer le plan « ${p.title} » ?\n\nLes tâches associées seront aussi supprimées.\nCette action est irréversible.`)) {
                    deletePlanMut.mutate()
                  }
                }}
                onKeyDown={(e) => {
                  if ((e.key === 'Enter' || e.key === ' ') && !deletePlanMut.isPending) {
                    e.preventDefault()
                    e.stopPropagation()
                    if (confirm(`Supprimer le plan « ${p.title} » ?`)) deletePlanMut.mutate()
                  }
                }}
                className={`p-1.5 rounded-md text-fg-muted hover:text-danger hover:bg-danger/10 transition ${
                  deletePlanMut.isPending ? 'opacity-40 cursor-wait' : 'cursor-pointer'
                }`}
                title="Supprimer ce plan d'action"
                aria-label="Supprimer"
              >
                <Trash2 size={13} />
              </span>
            </>
          )}
          <Link
            to="/action-plans/$id" params={{ id: p.id }}
            onClick={(e) => e.stopPropagation()}
            className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold inline-flex items-center gap-1"
          >
            Détail <ArrowUpRight size={11} />
          </Link>
        </div>
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

      {/* Modal édition rapide du plan (depuis la liste) */}
      <Modal
        open={showEdit}
        onClose={() => setShowEdit(false)}
        title={`Modifier "${p.title}"`}
        size="lg"
      >
        <QuickEditPlanForm
          plan={p}
          onSaved={() => {
            setShowEdit(false)
            qc.invalidateQueries({ queryKey: plansKeys.all })
            toast.success('Plan mis à jour')
          }}
          onCancel={() => setShowEdit(false)}
        />
      </Modal>
    </div>
  )
}

// ─── Formulaire d'édition compact (depuis la liste) ──────────
function QuickEditPlanForm({
  plan, onSaved, onCancel,
}: { plan: ActionPlan; onSaved: () => void; onCancel: () => void }) {
  const [title, setTitle] = useState(plan.title ?? '')
  const [description, setDescription] = useState(plan.description_md ?? '')
  const [status, setStatus] = useState(plan.status ?? 'open')
  const [startDate, setStartDate] = useState(plan.start_date ?? '')
  const [targetEndDate, setTargetEndDate] = useState(plan.target_end_date ?? '')

  const saveMut = useMutation({
    mutationFn: () =>
      apiClient.patch(`/action-plans/${plan.id}/`, {
        title,
        description_md: description,
        status,
        start_date: startDate || null,
        target_end_date: targetEndDate || null,
      }),
    onSuccess: () => onSaved(),
    onError: (e: any) => {
      toast.error(e?.response?.data?.detail || 'Échec de la sauvegarde')
    },
  })

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); saveMut.mutate() }}
      className="space-y-5"
    >
      <div>
        <label className="label">Titre</label>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required />
      </div>
      <div>
        <label className="label">Description</label>
        <textarea
          className="input min-h-[80px]"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="label">Statut</label>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            <option value="open">Ouvert</option>
            <option value="in_progress">En cours</option>
            <option value="blocked">Bloqué</option>
            <option value="completed">Terminé</option>
            <option value="cancelled">Annulé</option>
          </select>
        </div>
        <div>
          <label className="label">Démarrage</label>
          <input type="date" className="input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div>
          <label className="label">Échéance cible</label>
          <input type="date" className="input" value={targetEndDate} onChange={(e) => setTargetEndDate(e.target.value)} />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-4 border-t border-border">
        <button type="button" onClick={onCancel} className="px-4 py-2 rounded-md border border-border text-sm">
          Annuler
        </button>
        <PremiumButton type="submit" loading={saveMut.isPending}>
          Enregistrer
        </PremiumButton>
      </div>
    </form>
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

  // Surbrillance verte si tâche Fait à 100%
  const isDone100 = t.status === 'done' && (t.progress_percent ?? 0) >= 100
  return (
    <div className={`flex items-center gap-3 px-3 py-2.5 rounded transition group ${
      isDone100
        ? 'bg-success/10 border border-success/30'
        : t.is_overdue
          ? 'bg-danger/5 border border-danger/20'
          : 'bg-bg-elevated hover:bg-fg/[0.04]'
    }`}>
      <span className="text-copper-400 font-mono text-2xs tabular w-8 shrink-0 font-semibold">
        #{((t.order ?? (idx + 1))).toString().padStart(2, '0')}
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
          disabled={complete.isPending || (t.progress_percent ?? 0) < 100}
          title={
            (t.progress_percent ?? 0) < 100
              ? `La tâche doit être à 100% (actuellement : ${t.progress_percent ?? 0}%)`
              : 'Archiver la tâche'
          }
          className="text-2xs text-copper-400 hover:underline uppercase tracking-wider font-semibold shrink-0 disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed"
        >
          Archiver
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


/* ════════════════════════════════════════════════════════════
   Modal "Nouveau dossier" — création standalone (sans décision)
   ════════════════════════════════════════════════════════════ */

function NewActionPlanModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [targetEndDate, setTargetEndDate] = useState('')

  const create = useMutation({
    mutationFn: () => actionPlansApi.create({
      title: title.trim(),
      description_md: description.trim() || undefined,
      target_end_date: targetEndDate || undefined,
    } as any),
    onSuccess: () => {
      toast.success('Dossier créé.')
      qc.invalidateQueries({ queryKey: plansKeys.all })
      reset()
      onClose()
    },
    onError: (e: any) => {
      const data = e?.response?.data
      const msg = data?.detail
        || (data && typeof data === 'object'
          ? Object.entries(data).map(([k, v]: [string, any]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join(' · ')
          : null)
        || e?.message
        || 'Erreur création dossier.'
      toast.error(msg)
    },
  })

  function reset() {
    setTitle(''); setDescription(''); setTargetEndDate('')
  }

  return (
    <Modal open={open} onClose={() => { reset(); onClose() }} title="Nouveau dossier / plan d'action" size="md">
      <form
        onSubmit={(e) => { e.preventDefault(); if (title.trim()) create.mutate() }}
        className="space-y-4"
      >
        <p className="text-xs text-fg-muted">
          Crée un plan d'action autonome (sans décision parente). Les tâches
          pourront être ajoutées ensuite depuis la page du dossier.
        </p>

        <div>
          <label htmlFor="plan-title" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
            Titre <span className="text-danger">*</span>
          </label>
          <input
            id="plan-title" name="title" type="text" required autoFocus
            value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex : Refonte du système RH 2026"
            className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm focus:border-copper-500/50 outline-none"
            maxLength={250}
          />
        </div>

        <div>
          <label htmlFor="plan-desc" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
            Description (Markdown)
          </label>
          <textarea
            id="plan-desc" name="description"
            value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder="Objectifs, périmètre, contraintes…"
            className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm min-h-[100px] focus:border-copper-500/50 outline-none resize-y"
            rows={4}
          />
        </div>

        <div>
          <label htmlFor="plan-end" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
            Échéance cible
          </label>
          <input
            id="plan-end" name="target_end_date" type="date"
            value={targetEndDate} onChange={(e) => setTargetEndDate(e.target.value)}
            className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm focus:border-copper-500/50 outline-none"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={() => { reset(); onClose() }}
            className="px-4 py-2 text-sm text-fg-muted hover:text-fg rounded-md"
          >
            Annuler
          </button>
          <PremiumButton
            type="submit"
            disabled={!title.trim() || create.isPending}
            iconLeft={create.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          >
            {create.isPending ? 'Création…' : 'Créer le dossier'}
          </PremiumButton>
        </div>
      </form>
    </Modal>
  )
}
