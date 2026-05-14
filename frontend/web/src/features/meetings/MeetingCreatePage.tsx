import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { UserSelect } from '@/components/widgets/UserSelect'

import { meetingsApi } from './api'

const Schema = z.object({
  title: z.string().min(3, 'Titre trop court (min 3 caractères)'),
  meeting_type: z.enum(['regular', 'extraordinary', 'strategic', 'crisis']).default('regular'),
  description: z.string().optional(),
  scheduled_start: z.string().min(1, 'Date de début requise'),
  scheduled_end: z.string().min(1, 'Date de fin requise'),
  location: z.string().optional(),
  video_url: z.string().url().optional().or(z.literal('')),
  quorum_min: z.coerce.number().int().min(0).default(0),
})

type Values = z.infer<typeof Schema>

export function MeetingCreatePage() {
  const navigate = useNavigate()
  const { register, handleSubmit, formState: { errors }, setValue, watch } = useForm<Values>({
    resolver: zodResolver(Schema),
    defaultValues: { meeting_type: 'regular', quorum_min: 0 },
  })

  const chair = watch('chair' as any)
  const secretary = watch('secretary' as any)

  const mut = useMutation({
    mutationFn: (v: Values) => meetingsApi.create(v as any),
    onSuccess: (m) => {
      toast.success('Réunion créée')
      navigate({ to: '/meetings/$id', params: { id: m.id } })
    },
    onError: () => toast.error('Création impossible'),
  })

  return (
    <div className="min-h-full bg-bg-base">
      <header className="px-10 py-8 border-b border-border">
        <Link to="/meetings" className="inline-flex items-center gap-2 text-2xs uppercase tracking-widest text-fg-muted hover:text-fg transition mb-5">
          <ArrowLeft size={13} /> Toutes les réunions
        </Link>
        <div className="flex items-center gap-3 text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-3">
          <span className="divider-accent" /> Nouvelle session
        </div>
        <h1 className="serif text-editorial">Convoquer un comité.</h1>
      </header>

      <form onSubmit={handleSubmit((v) => mut.mutate(v))}
            className="max-w-3xl mx-auto px-10 py-10 space-y-6">

        <div>
          <label className="label">Titre *</label>
          <input className="input" {...register('title')} autoFocus />
          {errors.title && <span className="text-danger text-2xs mt-1 block">{errors.title.message}</span>}
        </div>

        <div>
          <label className="label">Description / contexte</label>
          <textarea className="input min-h-[100px]" {...register('description')} />
        </div>

        <div className="grid grid-cols-2 gap-5">
          <div>
            <label className="label">Type de réunion</label>
            <select className="input" {...register('meeting_type')}>
              <option value="regular">Ordinaire</option>
              <option value="extraordinary">Extraordinaire</option>
              <option value="strategic">Stratégique</option>
              <option value="crisis">De crise</option>
            </select>
          </div>
          <div>
            <label className="label">Quorum minimum</label>
            <input type="number" min={0} className="input" {...register('quorum_min')} />
          </div>
          <div>
            <label className="label">Début *</label>
            <input type="datetime-local" className="input" {...register('scheduled_start')} />
            {errors.scheduled_start && <span className="text-danger text-2xs mt-1 block">{errors.scheduled_start.message}</span>}
          </div>
          <div>
            <label className="label">Fin *</label>
            <input type="datetime-local" className="input" {...register('scheduled_end')} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-5">
          <div>
            <label className="label">Président de séance</label>
            <UserSelect value={chair ?? null}
                        onChange={(v) => setValue('chair' as any, v as any)}
                        placeholder="—" />
          </div>
          <div>
            <label className="label">Secrétaire</label>
            <UserSelect value={secretary ?? null}
                        onChange={(v) => setValue('secretary' as any, v as any)}
                        placeholder="—" />
          </div>
        </div>

        <div>
          <label className="label">Lieu</label>
          <input className="input" placeholder="Salle conseil, siège Paris…" {...register('location')} />
        </div>

        <div>
          <label className="label">Lien visioconférence</label>
          <input type="url" className="input" placeholder="https://teams.microsoft.com/…" {...register('video_url')} />
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t border-border">
          <PremiumButton type="button" variant="ghost" onClick={() => history.back()}>Annuler</PremiumButton>
          <PremiumButton loading={mut.isPending} type="submit">Créer la réunion</PremiumButton>
        </div>
      </form>
    </div>
  )
}
