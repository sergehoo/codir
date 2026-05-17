import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  AlertTriangle, ArrowLeft, Bell, CalendarDays, CheckCircle2,
  Clock, MessageSquare, Pencil, Send, Trash2, User as UserIcon, Users as UsersIcon, XCircle,
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
  const navigate = useNavigate()
  const [showPostpone, setShowPostpone] = useState(false)
  const [showCancel, setShowCancel] = useState(false)
  const [showEdit, setShowEdit] = useState(false)

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

  const deleteTask = useMutation({
    mutationFn: () => actionPlansApi.deleteTask(id),
    onSuccess: () => {
      toast.success('Tâche supprimée')
      qc.invalidateQueries({ queryKey: plansKeys.all })
      // Navigate back to the parent plan
      if (t?.action_plan) {
        navigate({ to: '/action-plans/$id', params: { id: t.action_plan } })
      } else {
        navigate({ to: '/action-plans' })
      }
    },
    onError: (e: any) => {
      toast.error(e?.response?.data?.detail || 'Suppression impossible')
    },
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
        eyebrow={`Tâche${t.order ? ` #${t.order.toString().padStart(2, '0')}` : ''}`}
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
                  disabled={(t.progress_percent ?? 0) < 100}
                  title={
                    (t.progress_percent ?? 0) < 100
                      ? `La tâche doit être à 100% pour être archivée (actuellement : ${t.progress_percent ?? 0}%)`
                      : 'Archiver la tâche'
                  }
                >Archiver</PremiumButton>
              </>
            )}
            {/* Modifier / Supprimer — protégés par can_modify */}
            {t.can_modify && (
              <>
                <PremiumButton
                  size="sm" variant="ghost"
                  iconLeft={<Pencil size={13} />}
                  onClick={() => setShowEdit(true)}
                >Modifier</PremiumButton>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`Supprimer la tâche "${t.title}" ?\n\nLes commentaires et preuves associées seront aussi supprimés.\n\nCette action est irréversible.`)) {
                      deleteTask.mutate()
                    }
                  }}
                  disabled={deleteTask.isPending}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border hover:border-danger/50 text-2xs font-semibold uppercase tracking-wider text-fg-muted hover:text-danger transition disabled:opacity-40"
                  title="Supprimer cette tâche"
                >
                  <Trash2 size={13} /> Supprimer
                </button>
              </>
            )}
            {t.can_modify === false && closed && (
              <span className="text-2xs uppercase tracking-wider text-fg-subtle italic">
                Lecture seule
              </span>
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
          icon={<UserIcon size={14} />} label="Responsable principal (lead)"
          value={t.assignee_detail?.full_name || '—'}
        />
        {((t.co_assignees_detail?.length ?? 0) > 0) && (
          <MetaCard
            icon={<UsersIcon size={14} />}
            label={`Co-responsables (${t.co_assignees_detail!.length})`}
            value={
              <div className="flex flex-wrap gap-1.5">
                {t.co_assignees_detail!.map((u) => (
                  <span
                    key={u.id}
                    className="inline-flex items-center gap-1.5 chip-quiet"
                    title={u.email}
                  >
                    <span className="w-5 h-5 rounded-full bg-copper-500/20 text-copper-400 inline-flex items-center justify-center text-2xs font-semibold uppercase">
                      {(u.first_name?.[0] || u.email[0] || '?').toUpperCase()}
                    </span>
                    {u.full_name || `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}
                  </span>
                ))}
              </div>
            }
          />
        )}
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
            <CommentRow key={c.id} comment={c} taskId={t.id} />
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
      <Modal
        open={showEdit}
        onClose={() => setShowEdit(false)}
        title={`Modifier "${t.title}"`}
        size="lg"
      >
        <EditTaskForm
          task={t as any}
          onSaved={() => {
            setShowEdit(false)
            qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', id] })
            qc.invalidateQueries({ queryKey: plansKeys.all })
            toast.success('Tâche mise à jour')
          }}
        />
      </Modal>
    </div>
  )
}

// ─── Composant ligne commentaire avec édition/suppression ──────────

function CommentRow({ comment, taskId }: { comment: any; taskId: string }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(comment.body_md)

  const updateMut = useMutation({
    mutationFn: () => actionPlansApi.updateComment(comment.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', taskId] })
      setEditing(false)
      toast.success('Commentaire modifié')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Échec'),
  })

  const deleteMut = useMutation({
    mutationFn: () => actionPlansApi.deleteComment(comment.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['action-tasks', 'detail', taskId] })
      toast.success('Commentaire supprimé')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Échec'),
  })

  return (
    <div className="card p-4 group">
      <div className="flex items-center gap-2 text-2xs uppercase tracking-wider text-fg-subtle mb-1.5">
        <span className="font-semibold text-fg-muted">
          {comment.author_detail?.full_name || comment.author_detail?.email || 'Utilisateur'}
        </span>
        <span>·</span>
        <span>{format(new Date(comment.created_at), "d MMM 'à' HH:mm", { locale: fr })}</span>
        {comment.updated_at && comment.updated_at !== comment.created_at && (
          <span className="italic">(modifié)</span>
        )}
        {comment.can_modify && !editing && (
          <div className="ml-auto flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
            <button
              type="button"
              onClick={() => { setBody(comment.body_md); setEditing(true) }}
              className="p-1 rounded hover:bg-bg-base text-fg-muted hover:text-copper-400"
              title="Modifier"
            >
              <Pencil size={12} />
            </button>
            <button
              type="button"
              onClick={() => {
                if (confirm('Supprimer ce commentaire ?')) deleteMut.mutate()
              }}
              disabled={deleteMut.isPending}
              className="p-1 rounded hover:bg-bg-base text-fg-muted hover:text-danger"
              title="Supprimer"
            >
              <Trash2 size={12} />
            </button>
          </div>
        )}
      </div>

      {editing ? (
        <div className="space-y-2">
          <textarea
            className="input w-full min-h-[80px] text-sm"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="text-2xs uppercase tracking-wider text-fg-muted px-3 py-1.5 rounded hover:bg-bg-base"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={() => updateMut.mutate()}
              disabled={!body.trim() || updateMut.isPending}
              className="text-2xs uppercase tracking-wider bg-copper-500 hover:bg-copper-400 text-white px-3 py-1.5 rounded font-semibold disabled:opacity-40"
            >
              {updateMut.isPending ? 'Sauvegarde…' : 'Enregistrer'}
            </button>
          </div>
        </div>
      ) : (
        <div className="text-sm whitespace-pre-wrap">{comment.body_md}</div>
      )}
    </div>
  )
}

// ─── Modal d'édition d'une tâche ─────────────────────────────────────

function EditTaskForm({
  task, onSaved,
}: { task: any; onSaved: () => void }) {
  const [title, setTitle] = useState(task.title ?? '')
  const [description, setDescription] = useState(task.description_md ?? '')
  const [priority, setPriority] = useState(task.priority ?? 'medium')
  const [status, setStatus] = useState(task.status ?? 'todo')
  const [progress, setProgress] = useState(task.progress_percent ?? 0)
  const [dueDate, setDueDate] = useState(task.due_date ?? '')
  const [order, setOrder] = useState<number>(task.order ?? 0)
  const [assignee, setAssignee] = useState<string>(task.assignee ?? '')
  const [coAssignees, setCoAssignees] = useState<string[]>(task.co_assignees ?? [])

  // Liste des users de l'org pour les selects
  const { data: users } = useQuery<any[]>({
    queryKey: ['users', 'org-mini'],
    queryFn: async () => {
      const { apiClient } = await import('@/api/client')
      const r = await apiClient.get('/auth/users/?page_size=200')
      const data: any = r.data
      return Array.isArray(data) ? data : (data?.results ?? [])
    },
    staleTime: 5 * 60_000,
  })

  const saveMut = useMutation({
    mutationFn: () => actionPlansApi.updateTask(task.id, {
      title,
      description_md: description,
      priority,
      status,
      progress_percent: progress,
      due_date: dueDate || null,
      order: order > 0 ? order : undefined,
      assignee: assignee || null,
      co_assignees: coAssignees,
    } as any),
    onSuccess: () => onSaved(),
    onError: (e: any) => {
      const msg = e?.response?.data?.detail || 'Échec de la sauvegarde'
      toast.error(msg)
    },
  })

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); saveMut.mutate() }}
      className="space-y-5"
    >
      <div className="grid grid-cols-[100px_1fr] gap-3">
        <div>
          <label className="label">N° d'ordre</label>
          <input
            type="number"
            min={1}
            className="input tabular"
            value={order || ''}
            onChange={(e) => setOrder(Number(e.target.value) || 0)}
            placeholder="—"
            title="Position de la tâche dans le plan d'action (utilisée pour le tri)"
          />
        </div>
        <div>
          <label className="label">Titre</label>
          <input
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </div>
      </div>

      <div>
        <label className="label">Description</label>
        <textarea
          className="input min-h-[80px]"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Statut</label>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="todo">Non démarré</option>
            <option value="in_progress">En cours</option>
            <option value="blocked">Bloqué</option>
            <option value="overdue">En retard</option>
            <option value="done">Terminé</option>
            <option value="cancelled">Annulé</option>
          </select>
        </div>
        <div>
          <label className="label">Priorité</label>
          <select className="input" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="low">Faible</option>
            <option value="medium">Moyenne</option>
            <option value="high">Élevée</option>
            <option value="critical">Critique</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Avancement ({progress}%)</label>
          <input
            type="range" min={0} max={100} step={5}
            value={progress}
            onChange={(e) => setProgress(Number(e.target.value))}
            className="w-full mt-2 accent-copper-500"
          />
        </div>
        <div>
          <label className="label">Date d'échéance</label>
          <input
            type="date" className="input"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </div>
      </div>

      {/* ─── Responsable principal ─── */}
      <div>
        <label className="label">Responsable principal (lead)</label>
        <select
          className="input"
          value={assignee}
          onChange={(e) => setAssignee(e.target.value)}
        >
          <option value="">— Non assigné —</option>
          {users?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name || `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}
            </option>
          ))}
        </select>
        <p className="text-2xs text-fg-subtle mt-1">
          Le lead reçoit les rappels et est affiché en avatar principal.
        </p>
      </div>

      {/* ─── Co-responsables ─── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="label !mb-0">
            Co-responsables ({coAssignees.length}
            {users && ` / ${users.length}`})
          </label>
          {users && users.length > 0 && (
            <div className="flex items-center gap-2 text-2xs">
              <button
                type="button"
                onClick={() =>
                  setCoAssignees(users.map((u: any) => u.id).filter((id: string) => id !== assignee))
                }
                disabled={coAssignees.length >= (users.length - (assignee ? 1 : 0))}
                className="uppercase tracking-wider text-copper-400 hover:underline font-semibold disabled:opacity-40"
              >
                Tout sélectionner
              </button>
              <span className="text-fg-subtle">·</span>
              <button
                type="button"
                onClick={() => setCoAssignees([])}
                disabled={coAssignees.length === 0}
                className="uppercase tracking-wider text-fg-muted hover:text-copper-400 font-semibold disabled:opacity-40"
              >
                Tout retirer
              </button>
            </div>
          )}
        </div>
        <div className="max-h-56 overflow-y-auto border border-border rounded-md p-2 space-y-0.5 bg-bg-base">
          {users?.map((u: any) => {
            const isPrimary = u.id === assignee
            const checked = coAssignees.includes(u.id)
            return (
              <label
                key={u.id}
                className={`flex items-center gap-2 text-sm px-2 py-1.5 rounded transition-colors ${
                  isPrimary ? 'opacity-50 cursor-not-allowed' : checked ? 'bg-copper-500/10 cursor-pointer' : 'hover:bg-bg-elevated cursor-pointer'
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={isPrimary}
                  onChange={(e) =>
                    setCoAssignees((prev) =>
                      e.target.checked
                        ? [...prev, u.id]
                        : prev.filter((p) => p !== u.id),
                    )
                  }
                  className="shrink-0 accent-copper-500"
                />
                <span className="flex-1 truncate">
                  {u.full_name || `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}
                </span>
                {isPrimary && (
                  <span className="text-2xs uppercase tracking-wider text-copper-500 font-semibold">
                    Lead
                  </span>
                )}
              </label>
            )
          })}
        </div>
        <p className="text-2xs text-fg-subtle mt-1">
          Tous les co-responsables peuvent modifier la tâche. Pas de rappels automatiques (seul le lead les reçoit).
        </p>
      </div>

      <div className="flex justify-end gap-2 pt-4 border-t border-border">
        <button
          type="button"
          onClick={() => onSaved()}
          className="px-4 py-2 rounded-md border border-border text-sm"
        >
          Annuler
        </button>
        <PremiumButton type="submit" loading={saveMut.isPending}>
          Enregistrer
        </PremiumButton>
      </div>
    </form>
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

