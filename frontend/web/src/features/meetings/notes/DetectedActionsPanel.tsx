import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ListChecks } from 'lucide-react'
import { toast } from 'sonner'

import { meetingsApi, meetingsKeys, type DetectedAction } from '../api'

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

      {pending.map((a) => (
        <div key={a.id} className="bg-bg-elevated border border-border rounded-md p-3 animate-fade-in-up">
          <div className="text-sm font-medium leading-snug">{a.title}</div>
          {a.assignee_detail && (
            <div className="text-2xs text-copper-400 mt-1">@{a.assignee_detail.full_name}</div>
          )}
          {!a.assignee_detail && a.assignee_mention && (
            <div className="text-2xs text-fg-subtle italic mt-1">
              @{a.assignee_mention} (non résolu)
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
      ))}
    </div>
  )
}
