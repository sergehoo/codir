import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import {
  ArrowLeft, CalendarClock, CheckCircle2, ClipboardList, Gavel,
  MapPin, PlayCircle, Plus, Trash2, Users, Video, XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { StatusBadge } from '@/components/widgets/StatusBadge'
import { UserSelect } from '@/components/widgets/UserSelect'
import { agendasApi, agendasKeys } from '@/features/agendas/api'
import { decisionsApi, decisionsKeys } from '@/features/decisions/api'

import { MeetingRecorderButton } from '@/features/meeting-recordings/components/MeetingRecorderButton'
import { recordingsApi } from '@/features/meeting-recordings/api'

import { meetingsApi, meetingsKeys } from './api'
import { CreateDecisionForm } from './CreateDecisionForm'
import { MeetingNotesSection } from './notes/MeetingNotesSection'

export function MeetingDetailPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const qc = useQueryClient()

  const { data: m } = useQuery({
    queryKey: meetingsKeys.detail(id),
    queryFn: () => meetingsApi.retrieve(id),
  })

  // Transitions
  const transition = useMutation({
    mutationFn: async (kind: 'schedule' | 'start' | 'complete' | 'cancel') =>
      (meetingsApi[kind] as (id: string) => Promise<unknown>)(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: meetingsKeys.detail(id) })
      toast.success('Action effectuée')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Action refusée'),
  })

  if (!m) return <div className="p-10 text-fg-subtle">Chargement…</div>

  return (
    <div className="min-h-full bg-bg-base">
      {/* ─── Masthead ──────────────────────────────────── */}
      <header className="px-10 py-8 border-b border-border">
        <Link to="/meetings" className="inline-flex items-center gap-2 text-2xs uppercase tracking-widest text-fg-muted hover:text-fg transition mb-5">
          <ArrowLeft size={13} /> Toutes les réunions
        </Link>
        <div className="flex items-center gap-3 text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-4">
          <span className="divider-accent" />
          <span>Comité de direction · {m.meeting_type}</span>
        </div>
        <div className="flex items-end justify-between gap-6 flex-wrap">
          <div className="flex-1 min-w-0">
            <h1 className="serif text-display leading-[1.05] mb-3">
              {m.title}
            </h1>
            <div className="flex items-center gap-5 text-sm text-fg-muted flex-wrap">
              <span className="inline-flex items-center gap-1.5">
                <CalendarClock size={14} strokeWidth={1.75} />
                {format(new Date(m.scheduled_start), "EEEE d MMMM yyyy 'à' HH:mm", { locale: fr })}
              </span>
              {m.location && (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin size={14} strokeWidth={1.75} /> {m.location}
                </span>
              )}
              {m.video_url && (
                <a href={m.video_url} target="_blank" rel="noreferrer"
                   className="inline-flex items-center gap-1.5 text-copper-400 hover:underline">
                  <Video size={14} strokeWidth={1.75} /> Visioconférence
                </a>
              )}
            </div>
          </div>
          <StatusBadge status={m.status} />
        </div>

        {/* Actions transition */}
        <div className="flex flex-wrap gap-2 mt-7">
          {m.status === 'draft' && (
            <PremiumButton onClick={() => transition.mutate('schedule')} iconLeft={<PlayCircle size={15} />}>
              Planifier
            </PremiumButton>
          )}
          {m.status === 'scheduled' && (
            <PremiumButton onClick={() => transition.mutate('start')} iconLeft={<PlayCircle size={15} />}>
              Démarrer la séance
            </PremiumButton>
          )}
          {m.status === 'in_progress' && (
            <PremiumButton onClick={() => transition.mutate('complete')} iconLeft={<CheckCircle2 size={15} />}>
              Clôturer et générer le PV
            </PremiumButton>
          )}
          {!['completed', 'cancelled'].includes(m.status) && (
            <PremiumButton variant="danger" onClick={() => transition.mutate('cancel')} iconLeft={<XCircle size={15} />}>
              Annuler
            </PremiumButton>
          )}
        </div>
      </header>

      {/* ─── Bloc info compact : onglets Participants / Agenda / Décisions ─── */}
      <MeetingInfoTabs meetingId={id} status={m.status} />

      {/* ─── Enregistrement audio IA (transcription + diarisation + résumé) ─── */}
      <MeetingRecordingSection meetingId={id} />

      {/* ─── Notes intelligentes (Tiptap + parser CODIR) ─── */}
      <MeetingNotesSection meetingId={id} />

      {/* ─── Compte rendu si dispo ─── */}
      {m.status === 'completed' && m.minutes_generated_at && (
        <section className="px-10 py-10 border-t border-border bg-bg-subtle/30">
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-5 flex items-center gap-3">
            <span className="divider-accent" /> Compte rendu officiel
          </div>
          <MinutesViewer meetingId={id} />
        </section>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   Section enregistrement audio IA — encart dans le détail réunion
   ═══════════════════════════════════════════════════════════════════ */

function MeetingRecordingSection({ meetingId }: { meetingId: string }) {
  // Récupère le recording le plus récent (s'il existe) pour reprendre l'état.
  const { data: recordings } = useQuery({
    queryKey: ['recordings', 'list', meetingId],
    queryFn: () => recordingsApi.listForMeeting(meetingId),
    staleTime: 5_000,
  })
  const latest = recordings?.[0] ?? null

  return (
    <section className="px-10 py-8 border-t border-border bg-bg-subtle/30">
      <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-5 flex items-center gap-3">
        <span className="divider-accent" /> Enregistrement & compte rendu IA
      </div>
      <div className="max-w-3xl">
        <MeetingRecorderButton
          meetingId={meetingId}
          existingRecording={latest as any}
        />
      </div>
    </section>
  )
}


/* ═══════════════════════════════════════════════════════════════════
   Bloc info compact — onglets Participants / Agenda / Décisions
   ═══════════════════════════════════════════════════════════════════ */

type Tab = 'participants' | 'agenda' | 'decisions'

function MeetingInfoTabs({ meetingId, status }: { meetingId: string; status: string }) {
  const [tab, setTab] = useState<Tab>('participants')

  // Compteurs légers (ne déclenchent pas de queries supplémentaires : les
  // mêmes querykeys que dans les panels seront servies depuis le cache).
  const { data: parts = [] } = useQuery({
    queryKey: meetingsKeys.participants(meetingId),
    queryFn: () => meetingsApi.listParticipants(meetingId),
  })
  const { data: meeting } = useQuery({
    queryKey: meetingsKeys.detail(meetingId),
    queryFn: () => meetingsApi.retrieve(meetingId),
  })
  const agendaId = (meeting as any)?.agenda?.id
  const { data: agenda } = useQuery({
    queryKey: agendasKeys.detail(agendaId ?? ''),
    queryFn: () => agendasApi.retrieve(agendaId!),
    enabled: !!agendaId,
  })
  const { data: decisionsData } = useQuery({
    queryKey: decisionsKeys.list({ meeting: meetingId } as any),
    queryFn: () => decisionsApi.list({ meeting: meetingId } as any),
  })
  const decisions = Array.isArray(decisionsData) ? decisionsData : (decisionsData?.results ?? [])

  const counters: Record<Tab, number> = {
    participants: parts.length,
    agenda: agenda?.items?.length ?? 0,
    decisions: decisions.length,
  }
  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'participants', label: 'Participants', icon: <Users size={13} /> },
    { id: 'agenda',       label: 'Ordre du jour', icon: <ClipboardList size={13} /> },
    { id: 'decisions',    label: 'Décisions',    icon: <Gavel size={13} /> },
  ]

  return (
    <section className="px-10 pt-6 pb-2">
      <div className="card overflow-hidden">
        {/* Barre d'onglets */}
        <nav
          className="flex items-stretch border-b border-border bg-bg-subtle/40"
          role="tablist"
        >
          {TABS.map((t) => {
            const active = tab === t.id
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-2 px-5 py-3 text-2xs uppercase tracking-wider font-semibold transition border-b-2 ${
                  active
                    ? 'border-copper-500 text-copper-400 bg-bg-elevated'
                    : 'border-transparent text-fg-muted hover:text-fg hover:bg-bg-elevated/40'
                }`}
              >
                {t.icon}
                <span>{t.label}</span>
                <span className={`text-2xs tabular px-1.5 py-0.5 rounded ${
                  active ? 'bg-copper-500/20 text-copper-400' : 'bg-fg/[0.06] text-fg-subtle'
                }`}>
                  {counters[t.id]}
                </span>
              </button>
            )
          })}
        </nav>

        {/* Contenu de l'onglet actif — hauteur max + scroll interne */}
        <div className="max-h-[420px] overflow-y-auto p-5">
          {tab === 'participants' && <ParticipantsPanel meetingId={meetingId} status={status} />}
          {tab === 'agenda'       && <AgendaPanel meetingId={meetingId} status={status} />}
          {tab === 'decisions'    && <DecisionsPanel meetingId={meetingId} />}
        </div>
      </div>
    </section>
  )
}

/* ═══════════════════════════════════════════════════════════════════
   Sub-panels
   ═══════════════════════════════════════════════════════════════════ */

function ParticipantsPanel({ meetingId, status }: { meetingId: string; status: string }) {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const locked = ['completed', 'cancelled'].includes(status)

  const { data: parts = [] } = useQuery({
    queryKey: meetingsKeys.participants(meetingId),
    queryFn: () => meetingsApi.listParticipants(meetingId),
  })
  const { data: attendances = [] } = useQuery({
    queryKey: meetingsKeys.attendance(meetingId),
    queryFn: () => meetingsApi.listAttendance(meetingId),
  })

  const remove = useMutation({
    mutationFn: (pid: string) => meetingsApi.removeParticipant(pid),
    onSuccess: () => { qc.invalidateQueries({ queryKey: meetingsKeys.participants(meetingId) }); toast.success('Retiré') },
  })
  const record = useMutation({
    mutationFn: ({ participant, statusVal }: { participant: string; statusVal: string }) =>
      meetingsApi.recordAttendance(meetingId, { participant, status: statusVal }),
    onSuccess: () => qc.invalidateQueries({ queryKey: meetingsKeys.attendance(meetingId) }),
  })

  const presentSet = new Map(attendances.map((a) => [a.participant, a.status]))

  return (
    <div>
      {!locked && (
        <div className="flex justify-end mb-2">
          <button
            onClick={() => setShowAdd(true)}
            className="text-2xs uppercase tracking-wider text-copper-400 hover:text-copper-500 font-semibold inline-flex items-center gap-1"
            title="Ajouter un participant"
          >
            <Plus size={12} /> Ajouter
          </button>
        </div>
      )}

      <ul className="divide-y divide-border">
        {parts.length === 0 && <li className="text-fg-subtle text-sm py-2">Aucun participant.</li>}
        {parts.map((p, i) => {
          const label = p.user_detail?.full_name || p.user_detail?.email || p.external_name || p.external_email
          const currentStatus = presentSet.get(p.id)
          return (
            <li key={p.id} className="py-3 first:pt-0">
              <div className="flex items-baseline gap-3">
                <span className="text-fg-subtle font-mono text-2xs tabular w-5">
                  {(i + 1).toString().padStart(2, '0')}
                </span>
                <div className="flex-1">
                  <div className="font-medium text-sm">{label}</div>
                  <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-0.5">{p.role}</div>
                </div>
                {!locked && (
                  <button onClick={() => remove.mutate(p.id)} className="text-fg-subtle hover:text-danger">
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
              {status === 'in_progress' && (
                <div className="flex gap-1.5 mt-2 ml-8">
                  {[
                    { v: 'present', label: 'Présent' },
                    { v: 'late',    label: 'En retard' },
                    { v: 'absent',  label: 'Absent' },
                  ].map((opt) => (
                    <button
                      key={opt.v}
                      onClick={() => record.mutate({ participant: p.id, statusVal: opt.v })}
                      className={`text-2xs px-2 py-0.5 rounded-md transition ${
                        currentStatus === opt.v
                          ? 'bg-copper-500/15 text-copper-400 border border-copper-500/30'
                          : 'text-fg-subtle border border-border hover:border-copper-500/30 hover:text-fg'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>

      <AddParticipantModal
        meetingId={meetingId} open={showAdd}
        onClose={() => setShowAdd(false)}
      />
    </div>
  )
}

function AddParticipantModal({
  meetingId, open, onClose,
}: { meetingId: string; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [user, setUser] = useState<string | null>(null)
  const [role, setRole] = useState('member')

  const add = useMutation({
    mutationFn: () => meetingsApi.addParticipant(meetingId, { user: (user as any), role: role as any }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: meetingsKeys.participants(meetingId) })
      qc.invalidateQueries({ queryKey: meetingsKeys.detail(meetingId) })
      toast.success('Participant ajouté')
      setUser(null); onClose()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Impossible'),
  })

  return (
    <Modal open={open} onClose={onClose} title="Ajouter un participant">
      <div className="space-y-4">
        <div>
          <label className="label">Utilisateur</label>
          <UserSelect value={user} onChange={setUser} placeholder="Choisir un membre…" />
        </div>
        <div>
          <label className="label">Rôle</label>
          <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="member">Membre</option>
            <option value="chair">Président</option>
            <option value="secretary">Secrétaire</option>
            <option value="invited">Invité</option>
            <option value="observer">Observateur</option>
          </select>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <PremiumButton variant="ghost" onClick={onClose}>Annuler</PremiumButton>
          <PremiumButton disabled={!user} loading={add.isPending} onClick={() => add.mutate()}>
            Ajouter
          </PremiumButton>
        </div>
      </div>
    </Modal>
  )
}

/* ─── Agenda panel ────────────────────────────────────────── */

function AgendaPanel({ meetingId, status }: { meetingId: string; status: string }) {
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [newItem, setNewItem] = useState({ title: '', priority: 'medium', estimated_duration_minutes: 15 })
  const [discussingItem, setDiscussingItem] = useState<string | null>(null)
  const [notes, setNotes] = useState('')

  // Récupérer l'agenda lié au meeting
  const { data: meeting } = useQuery({
    queryKey: meetingsKeys.detail(meetingId),
    queryFn: () => meetingsApi.retrieve(meetingId),
  })
  // L'API retourne agenda comme objet imbriqué côté DetailSerializer ; fallback à requête séparée
  const agendaId = (meeting as any)?.agenda?.id
  const { data: agenda } = useQuery({
    queryKey: agendasKeys.detail(agendaId ?? ''),
    queryFn: () => agendasApi.retrieve(agendaId!),
    enabled: !!agendaId,
  })

  const validate = useMutation({
    mutationFn: () => agendasApi.validate(agendaId!),
    onSuccess: () => { qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) }); qc.invalidateQueries({ queryKey: meetingsKeys.detail(meetingId) }); toast.success('Ordre du jour validé') },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Refusé'),
  })

  const addItem = useMutation({
    mutationFn: () => agendasApi.addItem(agendaId!, newItem as any),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) })
      setNewItem({ title: '', priority: 'medium', estimated_duration_minutes: 15 })
      setAdding(false)
      toast.success('Sujet ajouté')
    },
    onError: () => toast.error('Échec ajout'),
  })

  const discuss = useMutation({
    mutationFn: (itemId: string) => agendasApi.discussItem(itemId, notes),
    onSuccess: () => { qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) }); setDiscussingItem(null); setNotes(''); toast.success('Sujet traité') },
  })

  const items = agenda?.items ?? []
  const locked = agenda?.is_validated || ['completed', 'cancelled'].includes(status)

  if (!agendaId) {
    return (
      <p className="text-fg-subtle text-sm">Agenda non disponible.</p>
    )
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        {agenda?.is_validated ? <span className="chip-success">Validé</span> : <span className="chip-quiet">Brouillon</span>}
      </div>

      <ul className="divide-y divide-border">
        {items.length === 0 && <li className="text-fg-subtle text-sm py-2">Aucun sujet.</li>}
        {items.map((it, i) => (
          <li key={it.id} className="py-3 first:pt-0">
            <div className="flex items-baseline gap-3">
              <span className="text-fg-subtle font-mono text-2xs tabular w-5">
                {(i + 1).toString().padStart(2, '0')}
              </span>
              <div className="flex-1">
                <div className="font-medium text-sm">{it.title}</div>
                <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-1 flex items-center gap-2">
                  <span>{it.estimated_duration_minutes} min</span>
                  <span>·</span>
                  <span>{it.priority}</span>
                  {it.responsible_detail && <><span>·</span><span>{it.responsible_detail.full_name}</span></>}
                </div>
              </div>
              {it.status === 'discussed'
                ? <span className="chip-success text-2xs">Traité</span>
                : status === 'in_progress' && (
                  <button onClick={() => { setDiscussingItem(it.id); setNotes(it.discussion_notes_md ?? '') }}
                          className="text-2xs text-copper-400 hover:text-copper-500">Discuter ↗</button>
                )}
            </div>
            {discussingItem === it.id && (
              <div className="mt-3 ml-8 space-y-2">
                <textarea
                  className="input min-h-[80px]" placeholder="Notes de discussion / synthèse"
                  value={notes} onChange={(e) => setNotes(e.target.value)}
                />
                <div className="flex gap-2 justify-end">
                  <button className="text-2xs text-fg-muted" onClick={() => { setDiscussingItem(null); setNotes('') }}>Annuler</button>
                  <PremiumButton size="sm" onClick={() => discuss.mutate(it.id)} loading={discuss.isPending}>
                    Marquer traité
                  </PremiumButton>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>

      {!locked && (
        <div className="mt-4">
          {!adding && (
            <button onClick={() => setAdding(true)} className="btn-link">
              <Plus size={13} /> Ajouter un sujet
            </button>
          )}
          {adding && (
            <div className="space-y-3 mt-2 p-3 bg-bg-subtle rounded-lg border border-border">
              <input
                className="input" placeholder="Titre du sujet"
                value={newItem.title}
                onChange={(e) => setNewItem({ ...newItem, title: e.target.value })}
              />
              <div className="grid grid-cols-2 gap-3">
                <select className="input"
                        value={newItem.priority}
                        onChange={(e) => setNewItem({ ...newItem, priority: e.target.value })}>
                  <option value="low">Priorité faible</option>
                  <option value="medium">Priorité moyenne</option>
                  <option value="high">Priorité élevée</option>
                  <option value="critical">Critique</option>
                </select>
                <input
                  type="number" min={5} step={5}
                  className="input" placeholder="Durée (min)"
                  value={newItem.estimated_duration_minutes}
                  onChange={(e) => setNewItem({ ...newItem, estimated_duration_minutes: parseInt(e.target.value) || 15 })}
                />
              </div>
              <div className="flex justify-end gap-2">
                <button className="text-2xs text-fg-muted" onClick={() => setAdding(false)}>Annuler</button>
                <PremiumButton size="sm" disabled={!newItem.title} onClick={() => addItem.mutate()}>
                  Ajouter
                </PremiumButton>
              </div>
            </div>
          )}
        </div>
      )}

      {agenda && !agenda.is_validated && items.length > 0 && (
        <div className="mt-5 pt-5 border-t border-border">
          <PremiumButton variant="secondary" size="sm" onClick={() => validate.mutate()} loading={validate.isPending}>
            <CheckCircle2 size={14} /> Valider l'ordre du jour
          </PremiumButton>
        </div>
      )}
    </div>
  )
}

/* ─── Decisions panel ─────────────────────────────────────── */

function DecisionsPanel({ meetingId }: { meetingId: string }) {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)

  const { data } = useQuery({
    queryKey: decisionsKeys.list({ meeting: meetingId } as any),
    queryFn: () => decisionsApi.list({ meeting: meetingId } as any),
  })
  const decisions = Array.isArray(data) ? data : (data?.results ?? [])

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button
          onClick={() => setShowCreate(true)}
          className="text-2xs uppercase tracking-wider text-copper-400 hover:text-copper-500 font-semibold inline-flex items-center gap-1"
          title="Créer une décision"
        >
          <Plus size={12} /> Nouvelle décision
        </button>
      </div>

      <ul className="divide-y divide-border">
        {decisions.length === 0 && (
          <li className="text-fg-subtle text-sm py-2">Aucune décision pour cette réunion.</li>
        )}
        {decisions.map((d, i) => (
          <li key={d.id} className="py-3 first:pt-0">
            <Link to="/decisions/$id" params={{ id: d.id }} className="group block">
              <div className="flex items-baseline gap-3">
                <span className="text-fg-subtle font-mono text-2xs tabular w-5">
                  {(i + 1).toString().padStart(2, '0')}
                </span>
                <div className="flex-1">
                  <div className="font-medium text-sm group-hover:text-copper-400 transition">{d.title}</div>
                  <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-1">
                    {d.ref} · {d.priority}
                    {d.responsible_detail && <> · {d.responsible_detail.full_name}</>}
                  </div>
                </div>
                <StatusBadge status={d.status} />
              </div>
            </Link>
          </li>
        ))}
      </ul>

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nouvelle décision" size="md">
        <CreateDecisionForm
          meetingId={meetingId}
          onCreated={() => {
            qc.invalidateQueries({ queryKey: decisionsKeys.all })
            setShowCreate(false)
          }}
        />
      </Modal>
    </div>
  )
}

/* ─── Minutes (PV) ────────────────────────────────────────── */

function MinutesViewer({ meetingId }: { meetingId: string }) {
  const { data } = useQuery({
    queryKey: meetingsKeys.minutes(meetingId),
    queryFn: () => meetingsApi.minutes(meetingId),
  })
  const minutes: any = data
  if (!minutes) return <p className="text-fg-subtle text-sm">PV en cours de préparation…</p>
  return (
    <article className="card p-8 max-w-3xl mx-auto prose prose-invert prose-headings:serif prose-headings:font-medium">
      <div className="text-2xs uppercase tracking-widest text-copper-400 font-semibold mb-2">
        Compte rendu — Codir
      </div>
      <h2 className="serif text-h1 mb-6">{minutes.title}</h2>
      <div dangerouslySetInnerHTML={{ __html: minutes.body_html }} />
    </article>
  )
}
