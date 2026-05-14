import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  AlertTriangle, ArrowLeft, Bell, CalendarDays, CheckCircle2,
  Clock, MessageSquare, Send, User as UserIcon, XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { PriorityBadge } from '@/components/widgets/PriorityBadge'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { StatusBadge } from '@/components/widgets/StatusBadge'

import { actionPlansApi, plansKeys } from './api'
import { DelegateButton } from './DelegateTaskModal'

export function TaskDetailPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const qc = useQueryClient()
  const [showPostpone, setShowPostpone] = useState(false)
  const [showCancel, setShowCancel] = useState(false)

  const { data: t, isLoading } = useQuery({
    queryKey: ['action-tasks', 'detail', id],
    queryFn: () => actionPlansApi.taskDetail(id),
  })

  const complete = useMutation({
    mutationFn: () => actionPlansApi.completeTask(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', id] })
      qc.invalidateQueries({ queryKey: plansKeys.all })
      toast.success('Tâche clôturée')
    },
  })

  const remind = useMutation({
    mutationFn: async () => {
      const { taskActionsApi } = await import('@/features/notifications/api')
      return taskActionsApi.remind(id)
    },
    onSuccess: (res: any) => {
      toast.success(res?.detail || 'Rappel envoyé')
    },
    onError: () => toast.error('Échec — vérifiez les préférences de l\'assigné'),
  })

  if (isLoading) {
    return <div className="p-10 text-fg-subtle">Chargement…</div>
  }
  if (!t) {
    return <div className="p-10 text-fg-subtle">Tâche introuvable.</div>
  }

  const closed = t.status === 'done' || t.status === 'cancelled'

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Tâche"
        backTo={`/action-plans/${t.action_plan}`}
        backLabel="Retour au plan"
        title={t.title}
        description={t.action_plan_title}
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            {!closed && (
              <>
                <DelegateButton task={t as any} />
                <PremiumButton
                  size="sm" variant="ghost"
                  iconLeft={<CalendarDays size={13} />}
                  onClick={() => setShowPostpone(true)}
                >Reporter</PremiumButton>
                <PremiumButton
                  size="sm" variant="ghost"
                  iconLeft={<Bell size={13} />}
                  onClick={() => remind.mutate()}
                  loading={remind.isPending}
                >Rappeler</PremiumButton>
                <PremiumButton
                  size="sm" variant="secondary"
                  iconLeft={<XCircle size={13} />}
                  onClick={() => setShowCancel(true)}
                >Annuler</PremiumButton>
                <PremiumButton
                  size="sm" variant="primary"
                  iconLeft={<CheckCircle2 size={14} />}
                  onClick={() => complete.mutate()}
                  loading={complete.isPending}
                >Clôturer</PremiumButton>
              </>
            )}
          </div>
        }
      />

      {/* Méta + badges */}
      <section className="px-10 pt-6">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={t.status} />
          <PriorityBadge priority={t.priority} />
          {t.is_overdue && (
            <span className="chip-danger inline-flex items-center gap-1">
              <AlertTriangle size={11} /> En retard
            </span>
          )}
          {t.subsidiary_name && (
            <span className="chip-quiet">{t.subsidiary_name}</span>
          )}
        </div>
      </section>

      {/* Avancement */}
      <section className="px-10 py-6">
        <div className="card p-6 max-w-2xl">
          <div className="flex items-baseline justify-between mb-3">
            <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Avancement</span>
            <span className="serif text-h2 text-copper-400">{t.progress_percent}%</span>
          </div>
          <div className="h-2 bg-fg/[0.05] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-copper-gradient transition-all duration-1000"
              style={{ width: `${t.progress_percent}%` }}
            />
          </div>
          {!closed && (
            <ProgressSlider taskId={t.id} initial={t.progress_percent} />
          )}
        </div>
      </section>

      {/* Méta détaillée */}
      <section className="px-10 py-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <MetaCard
          icon={<UserIcon size={14} />} label="Assigné"
          value={t.assignee_detail?.full_name || '—'}
        />
        <MetaCard
          icon={<CalendarDays size={14} />} label="Échéance"
          value={t.due_date ? format(new Date(t.due_date), 'd MMMM yyyy', { locale: fr }) : 'Non définie'}
          highlight={t.is_overdue ? 'danger' : undefined}
        />
        {t.created_at && (
          <MetaCard
            icon={<Clock size={14} />} label="Créée le"
            value={format(new Date(t.created_at), 'd MMM yyyy', { locale: fr })}
          />
        )}
        {t.started_at && (
          <MetaCard
            icon={<Clock size={14} />} label="Démarrée"
            value={format(new Date(t.started_at), "d MMM yyyy 'à' HH:mm", { locale: fr })}
          />
        )}
        {t.completed_at && (
          <MetaCard
            icon={<CheckCircle2 size={14} />} label="Clôturée"
            value={format(new Date(t.completed_at), "d MMM yyyy 'à' HH:mm", { locale: fr })}
            highlight="success"
          />
        )}
        <MetaCard
          icon={<ArrowLeft size={14} />} label="Plan parent"
          value={
            <Link to="/action-plans/$id" params={{ id: t.action_plan }} className="text-copper-400 hover:underline">
              {t.action_plan_title || 'Voir le plan'}
            </Link>
          }
        />
      </section>

      {/* Description */}
      {t.description_md && (
        <section className="px-10 py-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Description</h2>
          </div>
          <div className="card p-6 prose prose-sm max-w-none whitespace-pre-wrap text-sm leading-relaxed">
            {t.description_md}
          </div>
        </section>
      )}

      {/* Commentaires */}
      <section className="px-10 py-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="divider-accent" />
          <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold flex items-center gap-2">
            <MessageSquare size={12} /> Activité & commentaires
          </h2>
          <span className="chip-quiet">{(t as any).comments?.length ?? 0}</span>
        </div>
        <div className="space-y-2">
          {((t as any).comments ?? []).length === 0 && (
            <p className="text-fg-subtle text-sm">Aucun commentaire pour l'instant.</p>
          )}
          {((t as any).comments ?? []).map((c: any) => (
            <div key={c.id} className="card p-4">
              <div className="flex items-center gap-2 text-2xs uppercase tracking-wider text-fg-subtle mb-1.5">
                <span className="font-semibold text-fg-muted">
                  {c.author_detail?.full_name || c.author_detail?.email || 'Utilisateur'}
                </span>
                <span>·</span>
                <span>{format(new Date(c.created_at), "d MMM 'à' HH:mm", { locale: fr })}</span>
              </div>
              <div className="text-sm whitespace-pre-wrap">{c.body_md}</div>
            </div>
          ))}
        </div>
        {!closed && (
          <CommentForm taskId={t.id} />
        )}
      </section>

      {/* Modals */}
      <Modal open={showPostpone} onClose={() => setShowPostpone(false)} title="Reporter l'échéance">
        <PostponeForm taskId={t.id} currentDue={t.due_date || ''} onDone={() => setShowPostpone(false)} />
      </Modal>
      <Modal open={showCancel} onClose={() => setShowCancel(false)} title="Annuler la tâche">
        <CancelForm taskId={t.id} onDone={() => setShowCancel(false)} />
      </Modal>
    </div>
  )
}

// ─── Sub-components ─────────────────────────────────────────

function MetaCard({ icon, label, value, highlight }: {
  icon: React.ReactNode
  label: string
  value: React.ReactNode
  highlight?: 'success' | 'danger' | 'warning'
}) {
  const tone =
    highlight === 'success' ? 'border-success/30 bg-success/5' :
    highlight === 'danger'  ? 'border-danger/30 bg-danger/5' :
    highlight === 'warning' ? 'border-warning/30 bg-warning/5' :
    ''
  return (
    <div className={`card p-4 ${tone}`}>
      <div className="flex items-center gap-2 text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-2">
        {icon} {label}
      </div>
      <div className="text-sm text-fg">{value}</div>
    </div>
  )
}

function ProgressSlider({ taskId, initial }: { taskId: string; initial: number }) {
  const qc = useQueryClient()
  const [value, setValue] = useState(initial)

  const update = useMutation({
    mutationFn: (v: number) => actionPlansApi.updateProgress(taskId, { progress_percent: v }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', taskId] })
      qc.invalidateQueries({ queryKey: plansKeys.all })
      toast.success('Avancement mis à jour')
    },
  })

  return (
    <div className="mt-5 flex items-center gap-3">
      <input
        type="range" min={0} max={100} step={5}
        value={value}
        onChange={(e) => setValue(parseInt(e.target.value))}
        className="flex-1 accent-copper-500"
      />
      <span className="text-sm tabular text-copper-400 w-12 text-right">{value}%</span>
      <PremiumButton
        size="sm"
        onClick={() => update.mutate(value)}
        loading={update.isPending}
        disabled={value === initial}
      >Enregistrer</PremiumButton>
    </div>
  )
}

function CommentForm({ taskId }: { taskId: string }) {
  const qc = useQueryClient()
  const [body, setBody] = useState('')
  const post = useMutation({
    mutationFn: async () => {
      const { apiClient } = await import('@/api/client')
      return (await apiClient.post(`/action-plans/tasks/${taskId}/comments/`, { body_md: body })).data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', taskId] })
      setBody('')
      toast.success('Commentaire ajouté')
    },
    onError: () => toast.error('Échec'),
  })
  return (
    <div className="card p-4 mt-3">
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Écrire un commentaire…"
        className="input min-h-[70px]"
      />
      <div className="flex justify-end mt-2">
        <PremiumButton
          size="sm"
          iconLeft={<Send size={12} />}
          onClick={() => post.mutate()}
          loading={post.isPending}
          disabled={!body.trim()}
        >Publier</PremiumButton>
      </div>
    </div>
  )
}

function PostponeForm({ taskId, currentDue, onDone }: { taskId: string; currentDue: string; onDone: () => void }) {
  const qc = useQueryClient()
  const [date, setDate] = useState(currentDue || '')
  const [reason, setReason] = useState('')
  const submit = useMutation({
    mutationFn: () => actionPlansApi.postponeTask(taskId, date, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', taskId] })
      qc.invalidateQueries({ queryKey: plansKeys.all })
      toast.success('Échéance reportée')
      onDone()
    },
    onError: () => toast.error('Échec'),
  })
  return (
    <div className="space-y-4">
      <div>
        <label className="label">Nouvelle échéance *</label>
        <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      <div>
        <label className="label">Motif</label>
        <textarea className="input min-h-[60px]" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <div className="flex justify-end gap-2">
        <PremiumButton variant="ghost" onClick={onDone}>Annuler</PremiumButton>
        <PremiumButton onClick={() => submit.mutate()} loading={submit.isPending} disabled={!date}>
          Reporter
        </PremiumButton>
      </div>
    </div>
  )
}

function CancelForm({ taskId, onDone }: { taskId: string; onDone: () => void }) {
  const qc = useQueryClient()
  const [reason, setReason] = useState('')
  const submit = useMutation({
    mutationFn: () => actionPlansApi.cancelTask(taskId, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', taskId] })
      qc.invalidateQueries({ queryKey: plansKeys.all })
      toast.success('Tâche annulée')
      onDone()
    },
    onError: () => toast.error('Échec'),
  })
  return (
    <div className="space-y-4">
      <div>
        <label className="label">Raison</label>
        <textarea className="input min-h-[80px]" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <div className="flex justify-end gap-2">
        <PremiumButton variant="ghost" onClick={onDone}>Garder</PremiumButton>
        <PremiumButton variant="danger" onClick={() => submit.mutate()} loading={submit.isPending}>
          Confirmer l'annulation
        </PremiumButton>
      </div>
    </div>
  )
}

