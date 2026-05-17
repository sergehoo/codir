/**
 * MeetingSeriesPage — CRUD des séries récurrentes (templates de réunions).
 *
 * Permet de :
 *  - Créer une série (ex: CODIR hebdo lundi 10h)
 *  - Voir les séries existantes + nombre d'instances générées
 *  - Activer/désactiver une série
 *  - Forcer la génération immédiate des instances
 *  - Supprimer une série (les Meetings existants gardent series=null)
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  Calendar, CheckCircle2, Clock, Play, Power, RotateCcw, Trash2, Users,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { apiClient } from '@/api/client'
import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import type { Paginated } from '@/types'

interface UserMini {
  id: string
  email: string
  first_name?: string
  last_name?: string
  full_name?: string
}

interface MeetingSeries {
  id: string
  title: string
  description: string
  frequency: 'weekly' | 'biweekly' | 'monthly'
  frequency_display: string
  day_of_week: number
  day_of_week_display: string
  day_of_month: number | null
  time: string
  duration_minutes: number
  meeting_type: string
  location: string
  video_url: string
  default_chair: string | null
  default_chair_detail?: UserMini | null
  default_secretary: string | null
  default_secretary_detail?: UserMini | null
  default_participants: string[]
  default_participants_detail?: UserMini[]
  generate_weeks_ahead: number
  last_generated_until: string | null
  is_active: boolean
  starts_on: string | null
  ends_on: string | null
  instances_count: number
}

const DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
const FREQUENCIES = [
  { value: 'weekly', label: 'Hebdomadaire' },
  { value: 'biweekly', label: 'Bi-mensuel (toutes les 2 sem.)' },
  { value: 'monthly', label: 'Mensuel' },
]

export function MeetingSeriesPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<MeetingSeries | null>(null)

  const { data: series, isLoading } = useQuery({
    queryKey: ['settings', 'meeting-series'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<MeetingSeries> | MeetingSeries[]>(
        '/meetings/series/',
      )
      return Array.isArray(r.data) ? r.data : r.data.results ?? []
    },
  })

  const generateMut = useMutation({
    mutationFn: (id: string) =>
      apiClient.post(`/meetings/series/${id}/generate-now/`),
    onSuccess: (r) => {
      toast.success(`${(r.data as any).instances_created} nouvelles réunions générées`)
      qc.invalidateQueries({ queryKey: ['settings', 'meeting-series'] })
      qc.invalidateQueries({ queryKey: ['meetings'] })
    },
    onError: () => toast.error('Échec de la génération'),
  })

  const toggleActiveMut = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      apiClient.patch(`/meetings/series/${id}/`, { is_active: !isActive }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings', 'meeting-series'] }),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/meetings/series/${id}/`),
    onSuccess: () => {
      toast.success('Série supprimée (les réunions générées sont conservées)')
      qc.invalidateQueries({ queryKey: ['settings', 'meeting-series'] })
    },
    onError: () => toast.error('Suppression impossible'),
  })

  const list = series ?? []

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Paramètres"
        title="Séries de réunions"
        description="Templates récurrents qui génèrent automatiquement les CODIR."
        actions={
          <PremiumButton
            variant="primary" size="sm"
            onClick={() => { setEditing(null); setShowForm(true) }}
          >
            + Nouvelle série
          </PremiumButton>
        }
      />

      <section className="px-10 py-6">
        {isLoading && <SkeletonList rows={3} />}

        {!isLoading && list.length === 0 && (
          <div className="card p-12 text-center">
            <Calendar size={32} className="mx-auto text-fg-subtle mb-3" strokeWidth={1.5} />
            <h3 className="serif text-h2 mb-2">Aucune série configurée</h3>
            <p className="text-fg-muted text-sm max-w-md mx-auto mb-6">
              Créez votre première série récurrente pour automatiser la programmation
              de votre CODIR hebdomadaire.
            </p>
            <PremiumButton onClick={() => { setEditing(null); setShowForm(true) }}>
              + Créer une série
            </PremiumButton>
          </div>
        )}

        {list.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {list.map((s) => (
              <div key={s.id} className="card p-5">
                <div className="flex items-start gap-3 mb-4">
                  <div className={`w-10 h-10 rounded-lg grid place-items-center shrink-0 ${
                    s.is_active ? 'bg-copper-500/10 text-copper-500' : 'bg-fg/[0.05] text-fg-muted'
                  }`}>
                    <RotateCcw size={18} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="serif text-base font-semibold leading-tight">
                      {s.title}
                    </h3>
                    <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-1 flex items-center gap-2">
                      <span>{s.frequency_display}</span>
                      <span className="dot-muted" />
                      {s.frequency === 'monthly' && s.day_of_month
                        ? <span>Jour {s.day_of_month} du mois</span>
                        : <span>{s.day_of_week_display}</span>}
                      <span className="dot-muted" />
                      <Clock size={11} />
                      <span>{s.time.slice(0, 5)} · {s.duration_minutes}min</span>
                    </div>
                  </div>
                  {s.is_active ? (
                    <span className="px-2 py-0.5 rounded text-2xs font-semibold bg-green-100 text-green-800">
                      Active
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-2xs font-semibold bg-slate-100 text-slate-700">
                      Inactive
                    </span>
                  )}
                </div>

                {(s.location || s.default_chair_detail) && (
                  <div className="space-y-1 text-sm text-fg-muted mb-3">
                    {s.location && (
                      <div>📍 {s.location}</div>
                    )}
                    {s.default_chair_detail && (
                      <div>👤 Président : {s.default_chair_detail.full_name || s.default_chair_detail.email}</div>
                    )}
                    {s.default_participants_detail && s.default_participants_detail.length > 0 && (
                      <div className="flex items-center gap-1.5">
                        <Users size={12} />
                        <span>{s.default_participants_detail.length} participant(s) par défaut</span>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex items-center gap-2 text-2xs uppercase tracking-wider text-fg-subtle mb-4 pt-3 border-t border-border">
                  <CheckCircle2 size={11} />
                  <span>{s.instances_count} réunion(s) générée(s)</span>
                  {s.last_generated_until && (
                    <>
                      <span className="dot-muted" />
                      <span>Jusqu'au {format(new Date(s.last_generated_until), 'd MMM yyyy', { locale: fr })}</span>
                    </>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => generateMut.mutate(s.id)}
                    disabled={!s.is_active || generateMut.isPending}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-copper-500 hover:bg-copper-400 text-white text-2xs font-semibold disabled:opacity-40"
                  >
                    <Play size={12} /> Générer maintenant
                  </button>
                  <button
                    onClick={() => { setEditing(s); setShowForm(true) }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border hover:border-copper-500/30 text-2xs font-semibold"
                  >
                    Modifier
                  </button>
                  <button
                    onClick={() => toggleActiveMut.mutate({ id: s.id, isActive: s.is_active })}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border hover:border-copper-500/30 text-2xs font-semibold"
                  >
                    <Power size={12} /> {s.is_active ? 'Désactiver' : 'Activer'}
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Supprimer la série "${s.title}" ? Les ${s.instances_count} réunion(s) déjà générée(s) seront conservées.`)) {
                        deleteMut.mutate(s.id)
                      }
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border hover:border-danger/40 text-2xs font-semibold text-fg-muted hover:text-danger ml-auto"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <Modal
        open={showForm}
        onClose={() => { setShowForm(false); setEditing(null) }}
        title={editing ? `Modifier "${editing.title}"` : 'Nouvelle série'}
      >
        <SeriesForm
          initial={editing}
          onSaved={() => {
            setShowForm(false); setEditing(null)
            qc.invalidateQueries({ queryKey: ['settings', 'meeting-series'] })
          }}
        />
      </Modal>
    </div>
  )
}

// ─── Form ──────────────────────────────────────────────────────────

function SeriesForm({
  initial, onSaved,
}: { initial: MeetingSeries | null; onSaved: () => void }) {
  const isEdit = !!initial

  // Users de l'org pour les selects
  const { data: users } = useQuery<UserMini[]>({
    queryKey: ['users', 'org-mini'],
    queryFn: async () => {
      const r = await apiClient.get<UserMini[] | { results: UserMini[] }>('/auth/users/?page_size=200')
      const data = r.data
      return Array.isArray(data) ? data : (data?.results ?? [])
    },
  })

  const [title, setTitle] = useState(initial?.title ?? 'CODIR Kaydan')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [frequency, setFrequency] = useState(initial?.frequency ?? 'weekly')
  const [dayOfWeek, setDayOfWeek] = useState(initial?.day_of_week ?? 0)
  const [dayOfMonth, setDayOfMonth] = useState(initial?.day_of_month ?? 1)
  const [time, setTime] = useState(initial?.time?.slice(0, 5) ?? '10:00')
  const [durationMinutes, setDurationMinutes] = useState(initial?.duration_minutes ?? 180)
  const [location, setLocation] = useState(initial?.location ?? '')
  const [defaultChair, setDefaultChair] = useState(initial?.default_chair ?? '')
  const [defaultSecretary, setDefaultSecretary] = useState(initial?.default_secretary ?? '')
  const [participants, setParticipants] = useState<string[]>(initial?.default_participants ?? [])
  const [generateWeeksAhead, setGenerateWeeksAhead] = useState(initial?.generate_weeks_ahead ?? 12)
  const [isActive, setIsActive] = useState(initial?.is_active ?? true)

  const saveMut = useMutation({
    mutationFn: async () => {
      const payload: any = {
        title, description, frequency,
        day_of_week: dayOfWeek,
        day_of_month: frequency === 'monthly' ? dayOfMonth : null,
        time: `${time}:00`,
        duration_minutes: durationMinutes,
        location,
        default_chair: defaultChair || null,
        default_secretary: defaultSecretary || null,
        default_participants: participants,
        generate_weeks_ahead: generateWeeksAhead,
        is_active: isActive,
      }
      if (isEdit) {
        return apiClient.patch(`/meetings/series/${initial!.id}/`, payload)
      }
      return apiClient.post('/meetings/series/', payload)
    },
    onSuccess: () => {
      toast.success(isEdit ? 'Série modifiée' : 'Série créée — lancez "Générer maintenant" pour créer les réunions')
      onSaved()
    },
    onError: (e: any) => {
      const msg = e?.response?.data?.detail || JSON.stringify(e?.response?.data || {})
      toast.error(msg.slice(0, 200))
    },
  })

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); saveMut.mutate() }}
      className="space-y-5"
    >
      <div>
        <label className="label">Titre</label>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required />
      </div>

      <div>
        <label className="label">Description (optionnel)</label>
        <textarea
          className="input min-h-[60px]"
          value={description} onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Fréquence</label>
          <select className="input" value={frequency} onChange={(e) => setFrequency(e.target.value as any)}>
            {FREQUENCIES.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </div>
        {frequency === 'monthly' ? (
          <div>
            <label className="label">Jour du mois (1-28)</label>
            <input
              type="number" min={1} max={28}
              className="input"
              value={dayOfMonth} onChange={(e) => setDayOfMonth(Number(e.target.value))}
            />
          </div>
        ) : (
          <div>
            <label className="label">Jour de la semaine</label>
            <select className="input" value={dayOfWeek} onChange={(e) => setDayOfWeek(Number(e.target.value))}>
              {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Heure de début</label>
          <input
            type="time" className="input"
            value={time} onChange={(e) => setTime(e.target.value)}
          />
        </div>
        <div>
          <label className="label">Durée (minutes)</label>
          <input
            type="number" min={15} step={15}
            className="input"
            value={durationMinutes}
            onChange={(e) => setDurationMinutes(Number(e.target.value))}
          />
        </div>
      </div>

      <div>
        <label className="label">Lieu (optionnel)</label>
        <input
          className="input"
          placeholder="Salle Comex, Visio Teams…"
          value={location} onChange={(e) => setLocation(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Président par défaut</label>
          <select className="input" value={defaultChair} onChange={(e) => setDefaultChair(e.target.value)}>
            <option value="">— Aucun —</option>
            {users?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name || `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Rapporteur par défaut</label>
          <select className="input" value={defaultSecretary} onChange={(e) => setDefaultSecretary(e.target.value)}>
            <option value="">— Aucun —</option>
            {users?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name || `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="label">
          Participants par défaut ({participants.length})
        </label>
        <div className="max-h-48 overflow-y-auto border border-border rounded-md p-2 space-y-1 bg-bg-elevated">
          {users?.map((u) => (
            <label key={u.id} className="flex items-center gap-2 text-sm hover:bg-bg-base px-2 py-1 rounded">
              <input
                type="checkbox"
                checked={participants.includes(u.id)}
                onChange={(e) => {
                  setParticipants((prev) =>
                    e.target.checked
                      ? [...prev, u.id]
                      : prev.filter((p) => p !== u.id),
                  )
                }}
              />
              <span>{u.full_name || `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Générer à l'avance (semaines)</label>
          <input
            type="number" min={1} max={52}
            className="input"
            value={generateWeeksAhead}
            onChange={(e) => setGenerateWeeksAhead(Number(e.target.value))}
          />
          <p className="text-2xs text-fg-subtle mt-1">
            Recommandé : 12 (3 mois d'avance)
          </p>
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            <span>Série active (génération auto)</span>
          </label>
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-4 border-t border-border">
        <button
          type="button"
          onClick={() => onSaved()}
          className="px-4 py-2 rounded-md border border-border text-sm"
        >
          Annuler
        </button>
        <PremiumButton type="submit" loading={saveMut.isPending}>
          {isEdit ? 'Enregistrer' : 'Créer la série'}
        </PremiumButton>
      </div>
    </form>
  )
}
