import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
  const [coAssignees, setCoAssignees] = useState<string[]>([])
  const [dueDate, setDueDate] = useState('')

  // Liste des users pour les co-responsables
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

  const add = useMutation({
    mutationFn: () => actionPlansApi.addTask(planId, {
      title,
      description_md: description,
      priority: priority as any,
      assignee: assignee as any,
      co_assignees: coAssignees,
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
        <label className="label">Responsable principal (lead)</label>
        <UserSelect value={assignee} onChange={setAssignee} placeholder="Choisir un membre…" />
        <p className="text-2xs text-fg-subtle mt-1">
          Le lead reçoit les rappels automatiques.
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
        <div className="max-h-48 overflow-y-auto border border-border rounded-md p-2 space-y-0.5 bg-bg-base">
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
          Co-responsables : peuvent modifier la tâche (sans rappels auto).
        </p>
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
