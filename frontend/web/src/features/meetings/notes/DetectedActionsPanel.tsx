import { useMutation, useQueryClient } from '@tanstack/react-query'
import { format, parseISO } from 'date-fns'
import { fr } from 'date-fns/locale'
import { CalendarDays, CheckCircle2, Flame, ListChecks } from 'lucide-react'
import { toast } from 'sonner'

import { meetingsApi, meetingsKeys, type DetectedAction } from '../api'

const PRIORITY_LABEL: Record<string, { label: string; tone: string }> = {
  low:      { label: 'Faible',  tone: 'text-fg-subtle bg-fg/[0.05]' },
  medium:   { label: 'Moyenne', tone: 'text-blue-600 bg-blue-100/40' },
  high:     { label: 'Élevée',  tone: 'text-amber-700 bg-amber-100/50' },
  critical: { label: 'Critique', tone: 'text-red-700 bg-red-100/50' },
}

export function DetectedActionsPanel({
  meetingId,
  actions,
}: {
  meetingId: string
  actions: DetectedAction[]
}) {
  const qc = useQueryClient()
  const publish = useMutation({
    mutationFn: (daId: string) => meetingsApi.publishAction(meetingId, daId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: meetingsKeys.smartNotes(meetingId) })
      toast.success('Action publiée')
    },
  })

  const pending = actions.filter((a) => a.status === 'pending')

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <ListChecks size={13} className="text-copper-400" />
        <h3 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
          Actions orphelines
        </h3>
        <span className="chip-quiet">{pending.length}</span>
      </div>

      {pending.length === 0 && (
        <div className="text-2xs text-fg-subtle uppercase tracking-wider px-1 py-3">
          Toutes les actions sont rattachées à une décision.
        </div>
      )}

      {pending.map((a) => {
        const prio = a.priority && PRIORITY_LABEL[a.priority]
        return (
          <div key={a.id} className="bg-bg-elevated border border-border rounded-md p-3 animate-fade-in-up">
            <div className="text-sm font-medium leading-snug">{a.title}</div>

            {/* Méta : date / priorité / assignee */}
            <div className="flex flex-wrap items-center gap-2 mt-1.5">
              {a.due_date && (
                <span className="inline-flex items-center gap-1 text-2xs text-fg-muted bg-fg/[0.05] px-1.5 py-0.5 rounded">
                  <CalendarDays size={10} />
                  {format(parseISO(a.due_date), 'd MMM yyyy', { locale: fr })}
                </span>
              )}
              {prio && (
                <span className={`inline-flex items-center gap-1 text-2xs px-1.5 py-0.5 rounded font-semibold ${prio.tone}`}>
                  <Flame size={10} /> {prio.label}
                </span>
              )}
              {a.assignee_detail && (
                <span className="text-2xs text-copper-400 font-medium">
                  @{a.assignee_detail.full_name}
                </span>
              )}
              {!a.assignee_detail && a.assignee_mention && (
                <span className="text-2xs text-fg-subtle italic">
                  @{a.assignee_mention} (non résolu)
                </span>
              )}
            </div>

            {a.description_md && (
              <div className="text-2xs text-fg-muted mt-2 pl-2 border-l-2 border-border whitespace-pre-wrap">
                {a.description_md}
              </div>
            )}

            <button
              onClick={() => publish.mutate(a.id)}
              disabled={publish.isPending}
              className="mt-2 text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold inline-flex items-center gap-1"
            >
              <CheckCircle2 size={11} /> Publier
            </button>
          </div>
        )
      })}
    </div>
  )
}
