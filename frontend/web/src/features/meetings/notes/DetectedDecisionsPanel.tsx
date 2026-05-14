import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ChevronDown, ChevronRight, Scale, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { meetingsApi, meetingsKeys, type DetectedDecision } from '../api'

export function DetectedDecisionsPanel({
  meetingId,
  decisions,
}: {
  meetingId: string
  decisions: DetectedDecision[]
}) {
  const qc = useQueryClient()

  const publishOne = useMutation({
    mutationFn: (ddId: string) => meetingsApi.publishDecision(meetingId, ddId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: meetingsKeys.smartNotes(meetingId) })
      toast.success('Décision publiée')
    },
    onError: () => toast.error('Échec'),
  })

  const dismiss = useMutation({
    mutationFn: (ddId: string) => meetingsApi.dismissDecision(meetingId, ddId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: meetingsKeys.smartNotes(meetingId) })
      toast.success('Détection rejetée')
    },
  })

  const publishAll = useMutation({
    mutationFn: () => meetingsApi.generateDecisions(meetingId),
    onSuccess: (r: any) => {
      qc.invalidateQueries({ queryKey: meetingsKeys.smartNotes(meetingId) })
      const p = r?.published
      toast.success(`${p?.decisions || 0} décision(s) · ${p?.actions || 0} action(s) publiées`)
    },
  })

  const pending = decisions.filter((d) => d.status === 'pending')
  const published = decisions.filter((d) => d.status === 'published')

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <Scale size={13} className="text-copper-400" />
          <h3 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
            Décisions détectées
          </h3>
          <span className="chip-quiet">{decisions.length}</span>
        </div>
        {pending.length > 0 && (
          <button
            onClick={() => publishAll.mutate()}
            disabled={publishAll.isPending}
            className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold disabled:opacity-50"
          >
            Tout publier ↗
          </button>
        )}
      </div>

      {decisions.length === 0 && (
        <div className="text-2xs text-fg-subtle uppercase tracking-wider px-1 py-3">
          Tapez <code className="text-copper-400 font-mono">#</code> au début d'une ligne pour créer une décision.
        </div>
      )}

      {pending.map((d) => (
        <DecisionRow
          key={d.id} d={d}
          onPublish={() => publishOne.mutate(d.id)}
          onDismiss={() => dismiss.mutate(d.id)}
          busy={publishOne.isPending || dismiss.isPending}
        />
      ))}

      {published.length > 0 && (
        <details className="mt-4 pt-3 border-t border-border/60">
          <summary className="text-2xs uppercase tracking-widest text-fg-subtle cursor-pointer hover:text-fg-muted">
            Publiées ({published.length})
          </summary>
          <div className="mt-2 space-y-1.5">
            {published.map((d) => (
              <div key={d.id} className="text-2xs text-fg-subtle px-2 py-1.5 line-through opacity-70">
                {d.title}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

function DecisionRow({
  d, onPublish, onDismiss, busy,
}: {
  d: DetectedDecision
  onPublish: () => void
  onDismiss: () => void
  busy: boolean
}) {
  const [open, setOpen] = useState(true)
  return (
    <div className="bg-bg-elevated border border-copper-500/20 rounded-md overflow-hidden animate-fade-in-up">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left px-3 py-2.5 hover:bg-fg/[0.03] transition flex items-start gap-2"
      >
        {open
          ? <ChevronDown size={13} className="text-copper-400 mt-1 shrink-0" />
          : <ChevronRight size={13} className="text-fg-subtle mt-1 shrink-0" />}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium leading-snug text-fg">{d.title}</div>
          {d.actions.length > 0 && (
            <div className="text-2xs text-fg-subtle uppercase tracking-wider mt-1">
              {d.actions.length} action(s)
            </div>
          )}
        </div>
      </button>
      {open && d.actions.length > 0 && (
        <div className="px-3 pb-3 space-y-1">
          {d.actions.map((a) => (
            <div key={a.id} className="text-2xs px-3 py-1.5 bg-bg-subtle/40 rounded flex items-center gap-2">
              <span className="text-copper-400">→</span>
              <span className="flex-1 truncate">{a.title}</span>
              {a.assignee_detail && (
                <span className="text-copper-400 font-medium">@{a.assignee_detail.full_name.split(' ')[0]}</span>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-border/60 bg-bg-subtle/30">
        <button
          onClick={onPublish}
          disabled={busy}
          className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold disabled:opacity-50 inline-flex items-center gap-1"
        >
          <CheckCircle2 size={11} /> Publier
        </button>
        <button
          onClick={onDismiss}
          disabled={busy}
          className="text-2xs uppercase tracking-wider text-fg-subtle hover:text-danger disabled:opacity-50 inline-flex items-center gap-1 ml-auto"
        >
          <Trash2 size={11} /> Rejeter
        </button>
      </div>
    </div>
  )
}
