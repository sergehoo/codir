import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { UserSelect } from '@/components/widgets/UserSelect'
import { decisionsApi } from '@/features/decisions/api'

export function CreateDecisionForm({
  meetingId, agendaItemId, onCreated,
}: { meetingId: string; agendaItemId?: string; onCreated: () => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'critical'>('medium')
  const [impact, setImpact] = useState<'low' | 'medium' | 'high' | 'strategic'>('medium')
  const [responsible, setResponsible] = useState<string | null>(null)
  const [deadline, setDeadline] = useState('')
  const [isConfidential, setIsConfidential] = useState(false)

  const create = useMutation({
    mutationFn: () => decisionsApi.create({
      title, description_md: description, meeting: meetingId,
      agenda_item: agendaItemId, priority, impact,
      responsible: responsible as any,
      deadline: deadline || null as any,
      is_confidential: isConfidential,
    } as any),
    onSuccess: () => { toast.success('Décision créée'); onCreated() },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Refus création'),
  })

  return (
    <div className="space-y-4">
      <div>
        <label className="label">Titre *</label>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
      </div>
      <div>
        <label className="label">Description / motivation</label>
        <textarea className="input min-h-[100px]" value={description}
                  onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Priorité</label>
          <select className="input" value={priority} onChange={(e) => setPriority(e.target.value as any)}>
            <option value="low">Faible</option>
            <option value="medium">Moyenne</option>
            <option value="high">Élevée</option>
            <option value="critical">Critique</option>
          </select>
        </div>
        <div>
          <label className="label">Impact</label>
          <select className="input" value={impact} onChange={(e) => setImpact(e.target.value as any)}>
            <option value="low">Faible</option>
            <option value="medium">Moyen</option>
            <option value="high">Fort</option>
            <option value="strategic">Stratégique</option>
          </select>
        </div>
        <div>
          <label className="label">Responsable</label>
          <UserSelect value={responsible} onChange={setResponsible} placeholder="Choisir…" />
        </div>
        <div>
          <label className="label">Échéance</label>
          <input type="date" className="input" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm text-fg-muted cursor-pointer">
        <input type="checkbox" checked={isConfidential}
               onChange={(e) => setIsConfidential(e.target.checked)}
               className="accent-copper-500" />
        Décision confidentielle
      </label>
      <div className="flex justify-end gap-2 pt-2">
        <PremiumButton variant="ghost" onClick={onCreated}>Annuler</PremiumButton>
        <PremiumButton disabled={!title} loading={create.isPending} onClick={() => create.mutate()}>
          Créer
        </PremiumButton>
      </div>
    </div>
  )
}
