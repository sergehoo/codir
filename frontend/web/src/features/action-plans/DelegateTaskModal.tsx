import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { Send, UserPlus } from 'lucide-react'

import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { UserSelect } from '@/components/widgets/UserSelect'
import type { ActionTask } from '@/types'

import { actionPlansApi, plansKeys } from './api'

export function DelegateTaskModal({
  task,
  open,
  onClose,
  onDelegated,
}: {
  task: ActionTask
  open: boolean
  onClose: () => void
  onDelegated?: (t: ActionTask) => void
}) {
  const qc = useQueryClient()
  const [assignee, setAssignee] = useState<string | null>(null)
  const [note, setNote] = useState('')

  const mut = useMutation({
    mutationFn: () => actionPlansApi.delegateTask(task.id, assignee!, note || undefined),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: plansKeys.all })
      qc.invalidateQueries({ queryKey: plansKeys.myTasks() })
      toast.success('Tâche déléguée')
      onDelegated?.(t)
      setAssignee(null); setNote('')
      onClose()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Échec de la délégation'),
  })

  const currentName = task.assignee_detail?.full_name || task.assignee_detail?.email || 'non assigné'

  return (
    <Modal open={open} onClose={onClose} title="Déléguer la tâche">
      <div className="space-y-5">
        <div className="card-quiet bg-bg-subtle/50 p-4">
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-1">
            Tâche
          </div>
          <div className="font-medium text-sm">{task.title}</div>
          <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-2 flex items-center gap-2">
            <span>Actuellement assigné à :</span>
            <span className="text-fg font-semibold normal-case">{currentName}</span>
          </div>
        </div>

        <div>
          <label className="label">Nouveau responsable *</label>
          <UserSelect value={assignee} onChange={setAssignee} placeholder="Choisir un membre…" />
        </div>

        <div>
          <label className="label">Note (optionnel)</label>
          <textarea
            className="input min-h-[80px]"
            value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="Contexte du transfert, instructions pour le nouveau responsable…"
          />
          <p className="text-2xs text-fg-subtle mt-1">
            La note sera ajoutée comme commentaire sur la tâche, et le nouvel assigné sera notifié.
          </p>
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t border-border">
          <PremiumButton variant="ghost" onClick={onClose}>Annuler</PremiumButton>
          <PremiumButton
            disabled={!assignee}
            loading={mut.isPending}
            iconLeft={<Send size={14} />}
            onClick={() => mut.mutate()}
          >
            Confirmer la délégation
          </PremiumButton>
        </div>
      </div>
    </Modal>
  )
}

/** Petit bouton "Déléguer" prêt-à-poser à côté d'une tâche. */
export function DelegateButton({
  task, className,
}: { task: ActionTask; className?: string }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(true) }}
        className={
          (className ?? '') +
          ' inline-flex items-center gap-1 text-2xs uppercase tracking-wider text-fg-muted hover:text-copper-400 transition font-semibold'
        }
        title="Déléguer cette tâche"
      >
        <UserPlus size={12} /> Déléguer
      </button>
      <DelegateTaskModal task={task} open={open} onClose={() => setOpen(false)} />
    </>
  )
}
