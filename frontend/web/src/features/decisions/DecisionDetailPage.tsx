import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  ArrowLeft, ArrowUpRight, CheckCircle2, Loader2, Lock, MessageSquare,
  Pencil, PlayCircle, Send, Sparkles, Trash2, XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { PriorityBadge } from '@/components/widgets/PriorityBadge'
import { StatusBadge } from '@/components/widgets/StatusBadge'
import { useAuthStore } from '@/stores/auth'

import { decisionsApi, decisionsKeys } from './api'

export function DecisionDetailPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const qc = useQueryClient()
  const navigate = useNavigate()
  const currentUser = useAuthStore((s) => s.user)
  const [editOpen, setEditOpen] = useState(false)

  const { data: d } = useQuery({
    queryKey: decisionsKeys.detail(id),
    queryFn: () => decisionsApi.retrieve(id),
  })
  const { data: history = [] } = useQuery({
    queryKey: decisionsKeys.history(id),
    queryFn: () => decisionsApi.history(id),
    enabled: !!d,
  })
  const { data: comments = [] } = useQuery({
    queryKey: decisionsKeys.comments(id),
    queryFn: () => decisionsApi.listComments(id),
    enabled: !!d,
  })

  const transition = useMutation({
    mutationFn: (kind: 'approve' | 'start' | 'complete' | 'cancel') =>
      (decisionsApi as any)[kind](id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: decisionsKeys.detail(id) }); toast.success('OK') },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Refus'),
  })

  const convert = useMutation({
    mutationFn: () => decisionsApi.convertToActionPlan(id),
    onSuccess: (plan) => {
      toast.success('Plan d\'action créé')
      navigate({ to: '/action-plans/$id', params: { id: plan.id } })
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Refus'),
  })

  const deleteMutation = useMutation({
    mutationFn: () => decisionsApi.remove(id),
    onSuccess: () => {
      toast.success('Décision supprimée.')
      qc.invalidateQueries({ queryKey: decisionsKeys.all })
      navigate({ to: '/decisions' })
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Suppression refusée.'),
  })

  function confirmDelete() {
    if (window.confirm(`Supprimer définitivement la décision « ${d?.title} » ?\n\nCette action est irréversible.`)) {
      deleteMutation.mutate()
    }
  }

  // Permissions : créateur OU executive/staff
  const canEdit = !!currentUser && (
    currentUser.is_executive
    || (d as any)?.created_by === currentUser.id
    || (d as any)?.created_by_detail?.id === currentUser.id
  )

  if (!d) return <div className="p-10 text-fg-subtle">Chargement…</div>

  return (
    <div className="min-h-full bg-bg-base">
      <header className="px-10 py-8 border-b border-border">
        <Link to="/decisions" className="inline-flex items-center gap-2 text-2xs uppercase tracking-widest text-fg-muted hover:text-fg transition mb-5">
          <ArrowLeft size={13} /> Toutes les décisions
        </Link>

        <div className="flex items-center gap-3 text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-4">
          <span className="divider-accent" />
          <span className="font-mono">{d.ref}</span>
          {d.is_confidential && (
            <>
              <span>·</span>
              <span className="inline-flex items-center gap-1 text-warning"><Lock size={11} /> Confidentielle</span>
            </>
          )}
        </div>

        <div className="flex items-end justify-between gap-6 flex-wrap">
          <h1 className="serif text-display leading-[1.05] flex-1 min-w-0">
            {d.title}
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={d.status} />
            <PriorityBadge priority={d.priority} />
          </div>
        </div>

        <div className="flex items-center gap-5 text-sm text-fg-muted flex-wrap mt-4">
          {d.responsible_detail && (
            <span>📌 {d.responsible_detail.full_name}</span>
          )}
          {d.deadline && (
            <span>⏰ Échéance : {format(new Date(d.deadline), 'd MMM yyyy', { locale: fr })}</span>
          )}
          {d.meeting && (
            <Link to="/meetings/$id" params={{ id: d.meeting }}
                  className="text-copper-400 hover:underline inline-flex items-center gap-1">
              Réunion associée <ArrowUpRight size={11} />
            </Link>
          )}
        </div>

        {/* Transitions */}
        <div className="flex flex-wrap gap-2 mt-7">
          {d.status === 'proposed' && (
            <PremiumButton onClick={() => transition.mutate('approve')} iconLeft={<CheckCircle2 size={15} />}>
              Valider
            </PremiumButton>
          )}
          {d.status === 'approved' && (
            <PremiumButton onClick={() => transition.mutate('start')} iconLeft={<PlayCircle size={15} />}>
              Démarrer l'exécution
            </PremiumButton>
          )}
          {(d.status === 'approved' || d.status === 'in_progress') && !d.has_action_plan && (
            <PremiumButton onClick={() => convert.mutate()} loading={convert.isPending} iconLeft={<Sparkles size={15} />}>
              Créer plan d'action
            </PremiumButton>
          )}
          {d.has_action_plan && (
            <PremiumButton variant="secondary" onClick={() => {
              // L'ID du plan n'est pas dans la décision, on requête à la volée
              // Ici on navigue vers la liste filtrée
            }} disabled>
              Plan d'action lié
            </PremiumButton>
          )}
          {d.status === 'in_progress' && (
            <PremiumButton variant="secondary" onClick={() => transition.mutate('complete')}>
              Clôturer
            </PremiumButton>
          )}
          {!['completed', 'cancelled'].includes(d.status) && (
            <PremiumButton variant="danger" onClick={() => transition.mutate('cancel')} iconLeft={<XCircle size={15} />}>
              Annuler
            </PremiumButton>
          )}

          {/* ─── Édition / Suppression — créateur ou exécutif ─── */}
          {canEdit && (
            <>
              <PremiumButton
                variant="secondary"
                onClick={() => setEditOpen(true)}
                iconLeft={<Pencil size={14} />}
              >
                Modifier
              </PremiumButton>
              <button
                type="button"
                onClick={confirmDelete}
                disabled={deleteMutation.isPending}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md text-sm font-semibold text-danger hover:bg-danger/10 border border-danger/30 transition"
                title="Supprimer définitivement"
              >
                {deleteMutation.isPending
                  ? <Loader2 size={14} className="animate-spin" />
                  : <Trash2 size={14} />}
                Supprimer
              </button>
            </>
          )}
        </div>
      </header>

      <EditDecisionModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        decision={d}
      />

      <div className="px-10 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Col 1 — Description + commentaires */}
        <div className="lg:col-span-2 space-y-8">
          <section className="card p-6">
            <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-4 flex items-center gap-3">
              <span className="divider-accent" /> Motivation
            </div>
            {d.description_md ? (
              <p className="text-fg leading-relaxed whitespace-pre-wrap">{d.description_md}</p>
            ) : (
              <p className="text-fg-subtle text-sm italic">Aucune description fournie.</p>
            )}
          </section>

          {/* Commentaires */}
          <section className="card p-6">
            <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-4 flex items-center gap-3">
              <span className="divider-accent" /> Échanges
              <span className="ml-auto chip-quiet">{comments.length}</span>
            </div>

            <CommentList id={id} comments={comments} />
            <CommentForm id={id} />
          </section>
        </div>

        {/* Col 2 — Timeline historique */}
        <aside className="space-y-8">
          <section className="card p-6">
            <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-5 flex items-center gap-3">
              <span className="divider-accent" /> Chronologie
            </div>
            <Timeline events={history} createdAt={d.created_at} />
          </section>
        </aside>
      </div>
    </div>
  )
}

function CommentList({ id: _id, comments }: { id: string; comments: any[] }) {
  if (comments.length === 0) {
    return <p className="text-fg-subtle text-sm italic mb-4 flex items-center gap-2">
      <MessageSquare size={14} /> Pas d'échange pour le moment.
    </p>
  }
  return (
    <ul className="space-y-4 mb-6">
      {comments.map((c) => (
        <li key={c.id} className="flex gap-3">
          <div className="w-8 h-8 rounded-full bg-copper-gradient grid place-items-center text-white text-2xs font-medium shrink-0">
            {(c.author_detail?.first_name?.[0] || '?').toUpperCase()}
          </div>
          <div className="flex-1">
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-medium">{c.author_detail?.full_name}</span>
              <span className="text-2xs text-fg-subtle uppercase tracking-wider">
                {format(new Date(c.created_at), "d MMM 'à' HH:mm", { locale: fr })}
              </span>
            </div>
            <p className="text-sm text-fg-muted mt-1 whitespace-pre-wrap">{c.body_md}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}

function CommentForm({ id }: { id: string }) {
  const qc = useQueryClient()
  const [body, setBody] = useState('')
  const post = useMutation({
    mutationFn: () => decisionsApi.addComment(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: decisionsKeys.comments(id) })
      setBody('')
    },
  })
  return (
    <div className="flex gap-2 items-start pt-4 border-t border-border">
      <textarea
        className="input flex-1 min-h-[60px]"
        placeholder="Ajouter un commentaire…"
        value={body} onChange={(e) => setBody(e.target.value)}
      />
      <PremiumButton size="sm" disabled={!body.trim()} loading={post.isPending}
                     onClick={() => post.mutate()} iconLeft={<Send size={13} />}>
        Envoyer
      </PremiumButton>
    </div>
  )
}

function Timeline({ events, createdAt }: { events: any[]; createdAt: string }) {
  const items = [
    { event: 'created', description: 'Décision créée', created_at: createdAt },
    ...events,
  ].slice().reverse()
  return (
    <ol className="space-y-5 relative ml-2 border-l border-border pl-6">
      {items.map((e, i) => (
        <li key={i} className="relative">
          <span className="absolute -left-[27px] top-1.5 w-2 h-2 rounded-full bg-copper-500 ring-4 ring-bg-elevated" />
          <div className="text-2xs uppercase tracking-widest text-copper-400 font-semibold">
            {e.event}
          </div>
          <div className="text-sm text-fg mt-0.5">{e.description || '—'}</div>
          <div className="text-2xs text-fg-subtle mt-1 uppercase tracking-wider">
            {format(new Date(e.created_at), "d MMM yyyy 'à' HH:mm", { locale: fr })}
            {e.actor_detail && <> · {e.actor_detail.full_name}</>}
          </div>
        </li>
      ))}
    </ol>
  )
}


/* ════════════════════════════════════════════════════════════
   Modal d'édition d'une décision existante (PATCH)
   ════════════════════════════════════════════════════════════ */

function EditDecisionModal({
  open, onClose, decision,
}: { open: boolean; onClose: () => void; decision: any }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState(decision?.title ?? '')
  const [description, setDescription] = useState(decision?.description_md ?? '')
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'critical'>(
    decision?.priority ?? 'medium',
  )
  const [deadline, setDeadline] = useState(decision?.deadline ?? '')
  const [isConfidential, setIsConfidential] = useState(!!decision?.is_confidential)

  // Resync l'état quand on ré-ouvre la modal sur une autre décision
  useState(() => {
    if (open) {
      setTitle(decision?.title ?? '')
      setDescription(decision?.description_md ?? '')
      setPriority(decision?.priority ?? 'medium')
      setDeadline(decision?.deadline ?? '')
      setIsConfidential(!!decision?.is_confidential)
    }
    return undefined
  })

  const update = useMutation({
    mutationFn: () => decisionsApi.update(decision.id, {
      title: title.trim(),
      description_md: description,
      priority,
      deadline: deadline || null,
      is_confidential: isConfidential,
    } as any),
    onSuccess: () => {
      toast.success('Décision mise à jour.')
      qc.invalidateQueries({ queryKey: decisionsKeys.detail(decision.id) })
      qc.invalidateQueries({ queryKey: decisionsKeys.all })
      onClose()
    },
    onError: (e: any) => {
      const data = e?.response?.data
      const msg = data?.detail
        || (data && typeof data === 'object'
          ? Object.entries(data).map(([k, v]: [string, any]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join(' · ')
          : null)
        || e?.message
        || 'Modification refusée.'
      toast.error(msg)
    },
  })

  return (
    <Modal open={open} onClose={onClose} title={`Modifier — ${decision?.ref ?? ''}`} size="md">
      <form
        onSubmit={(e) => { e.preventDefault(); if (title.trim()) update.mutate() }}
        className="space-y-4"
      >
        <div>
          <label htmlFor="edit-title" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
            Titre <span className="text-danger">*</span>
          </label>
          <input
            id="edit-title" name="title" type="text" required
            value={title} onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm focus:border-copper-500/50 outline-none"
            maxLength={250}
          />
        </div>

        <div>
          <label htmlFor="edit-desc" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
            Description (Markdown)
          </label>
          <textarea
            id="edit-desc" name="description"
            value={description} onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm min-h-[120px] focus:border-copper-500/50 outline-none resize-y"
            rows={5}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="edit-prio" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
              Priorité
            </label>
            <select
              id="edit-prio" name="priority"
              value={priority} onChange={(e) => setPriority(e.target.value as any)}
              className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm focus:border-copper-500/50 outline-none"
            >
              <option value="low">Faible</option>
              <option value="medium">Moyenne</option>
              <option value="high">Élevée</option>
              <option value="critical">Critique</option>
            </select>
          </div>
          <div>
            <label htmlFor="edit-deadline" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
              Échéance
            </label>
            <input
              id="edit-deadline" name="deadline" type="date"
              value={deadline ? deadline.slice(0, 10) : ''}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm focus:border-copper-500/50 outline-none"
            />
          </div>
        </div>

        <label htmlFor="edit-conf" className="flex items-center gap-2 text-xs text-fg cursor-pointer">
          <input
            id="edit-conf" name="is_confidential" type="checkbox"
            checked={isConfidential} onChange={(e) => setIsConfidential(e.target.checked)}
            className="rounded border-border accent-copper-500"
          />
          Décision confidentielle (visible uniquement par les DG / exécutifs)
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-fg-muted hover:text-fg rounded-md"
          >
            Annuler
          </button>
          <PremiumButton
            type="submit"
            disabled={!title.trim() || update.isPending}
            iconLeft={update.isPending ? <Loader2 size={14} className="animate-spin" /> : <Pencil size={14} />}
          >
            {update.isPending ? 'Mise à jour…' : 'Enregistrer'}
          </PremiumButton>
        </div>
      </form>
    </Modal>
  )
}
