import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { UserSelect } from '@/components/widgets/UserSelect'

import { actionPlansApi, plansKeys } from './api'

export function AddTaskForm({
  planId,
  onCreated,
  onCancel,
}: {
  planId: string
  onCreated?: () => void
  onCancel?: () => void
}) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('medium')
  const [assignee, setAssignee] = useState<string | null>(null)
  const [dueDate, setDueDate] = useState('')

  const add = useMutation({
    mutationFn: () => actionPlansApi.addTask(planId, {
      title,
      description_md: description,
      priority: priority as any,
      assignee: assignee as any,
      due_date: (dueDate || null) as any,
    } as any),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: plansKeys.detail(planId) })
      qc.invalidateQueries({ queryKey: plansKeys.tasks(planId) })
      qc.invalidateQueries({ queryKey: plansKeys.list() })
      qc.invalidateQueries({ queryKey: plansKeys.stats() })
      qc.invalidateQueries({ queryKey: ['my-tasks'] })
      toast.success('Tâche créée')
      onCreated?.()
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || 'Échec de la création'
      toast.error(msg)
    },
  })

  return (
    <div className="space-y-4">
      <div>
        <label className="label">Titre *</label>
        <input
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          autoFocus
          placeholder="Ex. Préparer la note de cadrage"
        />
      </div>
      <div>
        <label className="label">Description</label>
        <textarea
          className="input min-h-[80px]"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optionnel — contexte, livrable attendu…"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Priorité</label>
          <select
            className="input"
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
          >
            <option value="low">Faible</option>
            <option value="medium">Moyenne</option>
            <option value="high">Élevée</option>
            <option value="critical">Critique</option>
          </select>
        </div>
        <div>
          <label className="label">Échéance</label>
          <input
            type="date"
            className="input"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </div>
      </div>
      <div>
        <label className="label">Assigné à</label>
        <UserSelect value={assignee} onChange={setAssignee} placeholder="Choisir un membre…" />
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <PremiumButton variant="ghost" onClick={onCancel ?? onCreated}>
          Annuler
        </PremiumButton>
        <PremiumButton
          disabled={!title}
          loading={add.isPending}
          onClick={() => add.mutate()}
        >
          Créer
        </PremiumButton>
      </div>
    </div>
  )
}
