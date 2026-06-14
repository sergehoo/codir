import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { ArrowUpRight, Filter, Loader2, Lock, Plus, Scale } from 'lucide-react'
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
  const [createOpen, setCreateOpen] = useState(false)

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
        actions={
          <PremiumButton
            onClick={() => setCreateOpen(true)}
            iconLeft={<Plus size={14} />}
          >
            Nouvelle décision
          </PremiumButton>
        }
      />

      <NewDecisionModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
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
            description={
              <>
                Créez-en depuis le panneau Décisions d'une réunion, ou
                {' '}
                <button
                  type="button"
                  onClick={() => setCreateOpen(true)}
                  className="text-copper-400 hover:underline font-semibold"
                >
                  ajoutez une décision standalone
                </button>
                .
              </>
            }
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


/* ════════════════════════════════════════════════════════════
   Modal "Nouvelle décision" — création standalone (sans réunion)
   ════════════════════════════════════════════════════════════ */

function NewDecisionModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'critical'>('medium')
  const [deadline, setDeadline] = useState('')
  const [isConfidential, setIsConfidential] = useState(false)

  const create = useMutation({
    mutationFn: () => decisionsApi.create({
      title: title.trim(),
      description_md: description.trim() || undefined,
      priority,
      deadline: deadline || undefined,
      is_confidential: isConfidential,
    } as any),
    onSuccess: () => {
      toast.success('Décision créée.')
      qc.invalidateQueries({ queryKey: decisionsKeys.all })
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
        || 'Erreur création décision.'
      toast.error(msg)
    },
  })

  function reset() {
    setTitle(''); setDescription(''); setPriority('medium')
    setDeadline(''); setIsConfidential(false)
  }

  return (
    <Modal open={open} onClose={() => { reset(); onClose() }} title="Nouvelle décision" size="md">
      <form
        onSubmit={(e) => { e.preventDefault(); if (title.trim()) create.mutate() }}
        className="space-y-4"
      >
        <div>
          <label htmlFor="dec-title" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
            Titre <span className="text-danger">*</span>
          </label>
          <input
            id="dec-title" name="title" type="text" required autoFocus
            value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex : Lancer l'audit de cybersécurité Q3"
            className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm focus:border-copper-500/50 outline-none"
            maxLength={250}
          />
        </div>

        <div>
          <label htmlFor="dec-desc" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
            Description (Markdown)
          </label>
          <textarea
            id="dec-desc" name="description"
            value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder="Contexte, motivation, livrables attendus…"
            className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm min-h-[100px] focus:border-copper-500/50 outline-none resize-y"
            rows={4}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="dec-prio" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
              Priorité
            </label>
            <select
              id="dec-prio" name="priority"
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
            <label htmlFor="dec-deadline" className="text-2xs uppercase tracking-wider text-fg-muted font-semibold block mb-1.5">
              Échéance
            </label>
            <input
              id="dec-deadline" name="deadline" type="date"
              value={deadline} onChange={(e) => setDeadline(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-bg-elevated border border-border text-sm focus:border-copper-500/50 outline-none"
            />
          </div>
        </div>

        <label htmlFor="dec-conf" className="flex items-center gap-2 text-xs text-fg cursor-pointer">
          <input
            id="dec-conf" name="is_confidential" type="checkbox"
            checked={isConfidential} onChange={(e) => setIsConfidential(e.target.checked)}
            className="rounded border-border accent-copper-500"
          />
          Décision confidentielle (visible uniquement par les DG / exécutifs)
        </label>

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
            {create.isPending ? 'Création…' : 'Créer la décision'}
          </PremiumButton>
        </div>
      </form>
    </Modal>
  )
}
