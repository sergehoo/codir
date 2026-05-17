import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { AlertTriangle, ArrowLeft, CheckCircle2, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { PriorityBadge } from '@/components/widgets/PriorityBadge'
import { StatusBadge } from '@/components/widgets/StatusBadge'

import { AddTaskForm } from './AddTaskForm'
import { actionPlansApi, plansKeys } from './api'
import { DelegateButton } from './DelegateTaskModal'

export function ActionPlanDetailPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [editingProgress, setEditingProgress] = useState<string | null>(null)
  const [progressValue, setProgressValue] = useState(0)

  const { data: p } = useQuery({
    queryKey: plansKeys.detail(id),
    queryFn: () => actionPlansApi.retrieve(id),
  })

  const complete = useMutation({
    mutationFn: (taskId: string) => actionPlansApi.completeTask(taskId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: plansKeys.detail(id) }); toast.success('Tâche clôturée') },
  })

  const updateProgress = useMutation({
    mutationFn: ({ taskId, value }: { taskId: string; value: number }) =>
      actionPlansApi.updateProgress(taskId, { progress_percent: value }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: plansKeys.detail(id) }); setEditingProgress(null) },
  })

  if (!p) return <div className="p-10 text-fg-subtle">Chargement…</div>

  const tasks = p.tasks ?? []
  const overdueCount = tasks.filter((t) => t.is_overdue).length

  return (
    <div className="min-h-full bg-bg-base">

      <header className="px-10 py-8 border-b border-border">
        <Link to="/action-plans" className="inline-flex items-center gap-2 text-2xs uppercase tracking-widest text-fg-muted hover:text-fg transition mb-5">
          <ArrowLeft size={13} /> Tous les plans
        </Link>

        <div className="flex items-center gap-3 text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-4">
          <span className="divider-accent" />
          <span>Plan d'action</span>
          {p.decision && (
            <>
              <span>·</span>
              <Link to="/decisions/$id" params={{ id: p.decision }} className="text-copper-400 hover:underline">
                Voir la décision liée
              </Link>
            </>
          )}
        </div>

        <div className="flex items-end justify-between gap-6 flex-wrap">
          <h1 className="serif text-display leading-[1.05] flex-1 min-w-0">{p.title}</h1>
          <StatusBadge status={p.status} />
        </div>

        <div className="flex items-center gap-6 text-sm text-fg-muted flex-wrap mt-4">
          {p.owner_detail && <span>📌 {p.owner_detail.full_name}</span>}
          {p.start_date && (
            <span>Démarrage : {format(new Date(p.start_date), 'd MMM yyyy', { locale: fr })}</span>
          )}
          {p.target_end_date && (
            <span>Cible : {format(new Date(p.target_end_date), 'd MMM yyyy', { locale: fr })}</span>
          )}
        </div>

        {/* Progress global */}
        <div className="max-w-md mt-5">
          <div className="flex items-baseline justify-between mb-1.5">
            <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Avancement global</span>
            <span className="serif text-h3 text-copper-400">{p.progress_percent}%</span>
          </div>
          <div className="h-1.5 bg-fg/[0.05] rounded-full overflow-hidden">
            <div className="h-full rounded-full bg-copper-gradient transition-all duration-1000"
                 style={{ width: `${p.progress_percent}%` }} />
          </div>
        </div>
      </header>

      <section className="px-10 py-10">
        <div className="flex items-baseline justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="divider-accent" />
            <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Tâches</span>
            <span className="chip-quiet">{tasks.length}</span>
            {overdueCount > 0 && (
              <span className="chip-danger inline-flex items-center gap-1">
                <AlertTriangle size={11} /> {overdueCount} en retard
              </span>
            )}
          </div>
          <PremiumButton size="sm" iconLeft={<Plus size={14} />} onClick={() => setShowAdd(true)}>
            Nouvelle tâche
          </PremiumButton>
        </div>

        <div className="card overflow-hidden">
          <table className="w-full text-left">
            <thead className="text-2xs uppercase tracking-widest text-fg-muted border-b border-border bg-bg-subtle/50">
              <tr>
                <th className="py-3 px-5 font-semibold w-10">#</th>
                <th className="py-3 px-5 font-semibold">Tâche</th>
                <th className="py-3 px-5 font-semibold">Priorité</th>
                <th className="py-3 px-5 font-semibold">Statut</th>
                <th className="py-3 px-5 font-semibold">Échéance</th>
                <th className="py-3 px-5 font-semibold">Avancement</th>
                <th className="py-3 px-5"></th>
              </tr>
            </thead>
            <tbody>
              {tasks.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-fg-subtle py-12 text-center text-sm">
                    Aucune tâche. Cliquez sur « Nouvelle tâche » pour commencer.
                  </td>
                </tr>
              )}
              {tasks.map((t, i) => (
                <tr key={t.id} className="border-b border-border last:border-0 hover:bg-fg/[0.02]">
                  <td className="py-4 px-5 text-fg-subtle font-mono text-2xs tabular">
                    {(i + 1).toString().padStart(2, '0')}
                  </td>
                  <td className="py-4 px-5">
                    <Link to="/tasks/$id" params={{ id: t.id }} className="font-medium text-sm hover:text-copper-400 transition">
                      {t.title}
                    </Link>
                    {t.assignee_detail && (
                      <div className="text-2xs text-fg-subtle uppercase tracking-wider mt-1">
                        → {t.assignee_detail.full_name}
                      </div>
                    )}
                  </td>
                  <td className="py-4 px-5"><PriorityBadge priority={t.priority} /></td>
                  <td className="py-4 px-5">
                    <StatusBadge status={t.status} />
                    {t.is_overdue && (
                      <div className="text-2xs text-danger uppercase tracking-wider mt-1 flex items-center gap-1">
                        <AlertTriangle size={10} /> Retard
                      </div>
                    )}
                  </td>
                  <td className="py-4 px-5 text-sm tabular text-fg-muted">
                    {t.due_date ? format(new Date(t.due_date), 'dd/MM/yyyy') : '—'}
                  </td>
                  <td className="py-4 px-5 min-w-[180px]">
                    {editingProgress === t.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="range" min={0} max={100}
                          value={progressValue}
                          onChange={(e) => setProgressValue(parseInt(e.target.value))}
                          className="flex-1 accent-copper-500"
                        />
                        <span className="text-sm tabular text-copper-400 w-9">{progressValue}%</span>
                        <button onClick={() => updateProgress.mutate({ taskId: t.id, value: progressValue })}
                                className="text-2xs text-copper-400 font-semibold">OK</button>
                        <button onClick={() => setEditingProgress(null)}
                                className="text-2xs text-fg-muted">✕</button>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setEditingProgress(t.id); setProgressValue(t.progress_percent) }}
                        className="flex items-center gap-2 w-full hover:bg-fg/[0.04] py-1 px-2 rounded transition group"
                        disabled={t.status === 'done' || t.status === 'cancelled'}
                      >
                        <div className="flex-1 h-1.5 bg-fg/[0.05] rounded-full overflow-hidden">
                          <div className="h-full rounded-full bg-copper-gradient"
                               style={{ width: `${t.progress_percent}%` }} />
                        </div>
                        <span className="text-2xs tabular text-fg-muted w-9 text-right">{t.progress_percent}%</span>
                      </button>
                    )}
                  </td>
                  <td className="py-4 px-5 text-right">
                    <div className="inline-flex items-center gap-3">
                      {t.status !== 'done' && t.status !== 'cancelled' && (
                        <>
                          <DelegateButton task={t} />
                          <button
                            onClick={() => complete.mutate(t.id)}
                            disabled={(t.progress_percent ?? 0) < 100}
                            title={
                              (t.progress_percent ?? 0) < 100
                                ? `La tâche doit être à 100% (actuellement : ${t.progress_percent ?? 0}%)`
                                : 'Archiver la tâche'
                            }
                            className="text-2xs text-copper-400 hover:underline uppercase tracking-wider font-semibold disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed"
                          >
                            Archiver
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Nouvelle tâche">
        <AddTaskForm planId={id} onCreated={() => setShowAdd(false)} />
      </Modal>
    </div>
  )
}

