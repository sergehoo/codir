/**
 * CommitmentsPanel — Lot 5 : engagements oraux détectés sur un recording.
 *
 * Affiche les `AIActionRequest` créées automatiquement par
 * `commitment_detection` après la génération du résumé. Statut visible
 * (en attente / confirmé / créé / annulé / échec) avec liens directs.
 *
 * Pour CONFIRMER un engagement, l'utilisateur va dans le sidebar IA qui
 * propose la création de tâche en un clic via l'AIActionConfirmationCard
 * (déjà existant Phase 3 du chat IA). Ici on présente juste l'état.
 */
import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, Check, Clock, Mic, X } from 'lucide-react'

import { cn } from '@/utils/cn'

import { recordingsApi } from '../api'
import type { CommitmentStatus, RecordingCommitment } from '../types/recording.types'


const STATUS_TONE: Record<CommitmentStatus, { bg: string; text: string; label: string; icon: typeof Clock }> = {
  pending:   { bg: 'bg-warning/10',  text: 'text-warning', label: 'À valider',   icon: Clock },
  confirmed: { bg: 'bg-info/10',     text: 'text-info',    label: 'Confirmé',    icon: Check },
  executed:  { bg: 'bg-success/10',  text: 'text-success', label: 'Tâche créée', icon: Check },
  cancelled: { bg: 'bg-fg/[0.05]',   text: 'text-fg-subtle', label: 'Annulé',    icon: X },
  failed:    { bg: 'bg-danger/10',   text: 'text-danger',  label: 'Échec',       icon: X },
}


export function CommitmentsPanel({ recordingId }: { recordingId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['recording', recordingId, 'commitments'],
    queryFn: () => recordingsApi.commitments(recordingId),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  if (isLoading) {
    return (
      <div className="card p-5">
        <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-3 flex items-center gap-2">
          <Mic size={11} className="text-copper-400" />
          Engagements oraux
        </div>
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <div key={i} className="h-14 bg-fg/[0.04] rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (isError) return null

  const results = data?.results ?? []
  if (results.length === 0) return null  // pas d'engagement → on cache la section

  const pendingCount = results.filter((r: RecordingCommitment) => r.status === 'pending').length

  return (
    <div className="card p-5">
      <header className="flex items-center justify-between mb-4">
        <div>
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold flex items-center gap-2">
            <Mic size={11} className="text-copper-400" />
            Engagements oraux détectés
          </div>
          <h3 className="text-h3 font-semibold mt-1">
            {results.length} engagement{results.length > 1 ? 's' : ''}
            {pendingCount > 0 && (
              <span className="ml-2 chip-copper text-2xs">{pendingCount} en attente</span>
            )}
          </h3>
          <p className="text-xs text-fg-muted mt-1">
            L'IA a identifié des promesses d'action prononcées en réunion. Confirmez
            depuis le sidebar pour créer la tâche automatiquement.
          </p>
        </div>
      </header>

      <ul className="divide-y divide-border">
        {results.map((c) => (
          <CommitmentRow key={c.id} c={c} />
        ))}
      </ul>
    </div>
  )
}


function CommitmentRow({ c }: { c: RecordingCommitment }) {
  const tone = STATUS_TONE[c.status]
  const Icon = tone.icon

  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex items-start gap-3">
        {/* Statut chip */}
        <span className={cn(
          'inline-flex items-center gap-1.5 px-2 py-1 rounded text-2xs uppercase tracking-wider font-semibold shrink-0',
          tone.bg, tone.text,
        )}>
          <Icon size={11} />
          {tone.label}
        </span>

        {/* Contenu */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="text-2xs uppercase tracking-wider text-fg-subtle font-semibold">
              {c.speaker_label}
            </span>
            {c.due_date && (
              <span className="text-2xs uppercase tracking-wider text-fg-subtle">
                · échéance {new Date(c.due_date).toLocaleDateString('fr-FR')}
              </span>
            )}
            {c.assignee_email && (
              <span className="text-2xs text-fg-subtle truncate">
                · {c.assignee_email}
              </span>
            )}
          </div>
          <div className="text-sm font-medium text-fg leading-snug mt-0.5">
            {c.title}
          </div>
          {c.evidence_quote && (
            <blockquote className="mt-1.5 text-xs text-fg-muted italic border-l-2 border-copper-500/30 pl-2 leading-relaxed">
              « {c.evidence_quote} »
            </blockquote>
          )}
          {c.status === 'failed' && c.error_message && (
            <div className="mt-1.5 text-xs text-danger">{c.error_message}</div>
          )}
          {c.status === 'executed' && c.result_object_id && c.result_object_type?.includes('actiontask') && (
            <a
              href={`/tasks/${c.result_object_id}`}
              className="mt-1.5 inline-flex items-center gap-1 text-2xs uppercase tracking-wider text-copper-400 font-semibold hover:underline"
            >
              Voir la tâche créée <ArrowUpRight size={11} />
            </a>
          )}
        </div>
      </div>
    </li>
  )
}
