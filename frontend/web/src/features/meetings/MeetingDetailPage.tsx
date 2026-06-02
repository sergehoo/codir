import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'

import { safeFormat } from '@/utils/safeDate'
import {
  ArrowLeft, CalendarClock, CheckCircle2, ClipboardList, Gavel,
  GripVertical, MapPin, Pencil, PlayCircle, Plus, Trash2, Users, Video, XCircle,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { StatusBadge } from '@/components/widgets/StatusBadge'
import { UserSelect } from '@/components/widgets/UserSelect'
import { cn } from '@/utils/cn'
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
  const [editOpen, setEditOpen] = useState(false)

  const { data: m } = useQuery({
    queryKey: meetingsKeys.detail(id),
    queryFn: () => meetingsApi.retrieve(id),
  })

  // Agenda : on en a besoin pour savoir si l'ODJ est validé (pré-requis pour démarrer).
  const agendaIdTop = (m as any)?.agenda?.id
  const { data: agendaTop } = useQuery({
    queryKey: agendasKeys.detail(agendaIdTop ?? ''),
    queryFn: () => agendasApi.retrieve(agendaIdTop!),
    enabled: !!agendaIdTop,
  })
  const agendaValidated = !!agendaTop?.is_validated
  const hasAgendaItems = (agendaTop?.items?.length ?? 0) > 0

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

  // Validation de l'ordre du jour — pré-requis pour démarrer la séance.
  const validateAgendaMutation = useMutation({
    mutationFn: () => agendasApi.validate(agendaIdTop!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaIdTop!) })
      qc.invalidateQueries({ queryKey: meetingsKeys.detail(id) })
      toast.success("Ordre du jour validé. Vous pouvez démarrer la séance.")
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Validation refusée"),
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
                {safeFormat(m.scheduled_start, "EEEE d MMMM yyyy 'à' HH:mm", { fallback: 'Date non définie' })}
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
            <>
              {/*
                CODIR cyclique : la validation de l'ODJ n'est pas un pré-requis
                bloquant — une réunion peut hériter de l'ODJ d'une séance
                précédente, ou démarrer en mode "crise" sans ODJ formel.
                On propose donc "Valider l'ODJ" en option (UX claire pour
                signaler le statut), mais "Démarrer" reste toujours actif.
              */}
              {agendaIdTop && !agendaValidated && hasAgendaItems && (
                <PremiumButton
                  variant="secondary"
                  onClick={() => validateAgendaMutation.mutate()}
                  iconLeft={<CheckCircle2 size={15} />}
                  disabled={validateAgendaMutation.isPending}
                >
                  Valider l'ordre du jour
                </PremiumButton>
              )}
              <PremiumButton
                onClick={() => transition.mutate('start')}
                iconLeft={<PlayCircle size={15} />}
              >
                Démarrer la séance
              </PremiumButton>
            </>
          )}
          {m.status === 'in_progress' && (
            <PremiumButton onClick={() => transition.mutate('complete')} iconLeft={<CheckCircle2 size={15} />}>
              Clôturer et générer le PV
            </PremiumButton>
          )}
          {/* Modifier la réunion — disponible tant qu'elle n'est pas clôturée */}
          {!['completed', 'cancelled'].includes(m.status) && (
            <PremiumButton
              variant="secondary"
              onClick={() => setEditOpen(true)}
              iconLeft={<Pencil size={15} />}
            >
              Modifier
            </PremiumButton>
          )}
          {!['completed', 'cancelled'].includes(m.status) && (
            <PremiumButton variant="danger" onClick={() => transition.mutate('cancel')} iconLeft={<XCircle size={15} />}>
              Annuler
            </PremiumButton>
          )}
        </div>
      </header>

      {/* Modal édition réunion */}
      <EditMeetingModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        meeting={m}
      />

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
    <section id="meeting-tabs" className="px-10 pt-6 pb-2">
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
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<any>(null)
  const [discussingItem, setDiscussingItem] = useState<string | null>(null)
  const [notes, setNotes] = useState('')

  // Drag-and-drop : on garde un état local pour l'optimistic update.
  // `dragOverId` = item au-dessus duquel on hover (pour drop zone visuelle).
  const [draggingId, setDraggingId] = useState<string | null>(null)
  const [dragOverId, setDragOverId] = useState<string | null>(null)

  // Récupérer l'agenda lié au meeting
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

  // Source de vérité locale des items : reflète le résultat backend, mais peut
  // être modifié temporairement pendant le drag-drop (optimistic).
  const [localItems, setLocalItems] = useState<any[]>([])
  useEffect(() => {
    setLocalItems(agenda?.items ?? [])
  }, [agenda?.items])

  const validate = useMutation({
    mutationFn: () => agendasApi.validate(agendaId!),
    onSuccess: () => { qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) }); qc.invalidateQueries({ queryKey: meetingsKeys.detail(meetingId) }); toast.success('Ordre du jour validé') },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Refusé'),
  })

  // Réutilisation ODJ séance précédente — visible si réunion dans une série.
  const seriesId = (meeting as any)?.series_id ?? (meeting as any)?.series?.id ?? null
  const copyFromPrevious = useMutation({
    mutationFn: () => agendasApi.copyFromPrevious(agendaId!),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) })
      if (data.copied > 0) {
        toast.success(
          `${data.copied} point${data.copied > 1 ? 's' : ''} reporté${data.copied > 1 ? 's' : ''} `
          + `depuis « ${data.source_meeting_title} »`,
        )
      } else if (data.source_meeting_id) {
        toast.info(`Séance précédente trouvée mais aucun point à reporter.`)
      } else {
        toast.info("Aucune séance précédente trouvée dans cette série.")
      }
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Échec de la copie.'),
  })

  // Réordonnancement — appelle l'endpoint reorder avec l'ordre courant.
  const reorder = useMutation({
    mutationFn: (orderedIds: string[]) => agendasApi.reorder(agendaId!, orderedIds),
    onSuccess: () => qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) }),
    onError: (e: any) => {
      // Rollback : on rafraîchit pour récupérer l'ordre serveur.
      qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) })
      toast.error(e?.response?.data?.detail ?? 'Réorganisation refusée.')
    },
  })

  // Suppression d'un item
  const deleteItem = useMutation({
    mutationFn: (itemId: string) => agendasApi.deleteItem(itemId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) })
      toast.success('Point supprimé')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Suppression refusée.'),
  })

  const discuss = useMutation({
    mutationFn: (itemId: string) => agendasApi.discussItem(itemId, notes),
    onSuccess: () => { qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId!) }); setDiscussingItem(null); setNotes(''); toast.success('Sujet traité') },
  })

  const locked = agenda?.is_validated || ['completed', 'cancelled'].includes(status)
  const items = localItems
  const canDrag = !locked && items.length > 1

  if (!agendaId) {
    return (
      <p className="text-fg-subtle text-sm">Agenda non disponible.</p>
    )
  }

  // ─── Drag-and-drop handlers (HTML5 natif) ───────────────────
  // Optimistic update : on réordonne localItems immédiatement à la fin du drop,
  // puis on appelle reorder. Si erreur, l'invalidation du cache rétablit l'ordre.
  const handleDragStart = (e: React.DragEvent, id: string) => {
    if (!canDrag) return
    setDraggingId(id)
    e.dataTransfer.effectAllowed = 'move'
    // Indispensable pour Firefox : sans setData, le drag n'est pas reconnu.
    e.dataTransfer.setData('text/plain', id)
  }
  const handleDragOver = (e: React.DragEvent, overId: string) => {
    if (!canDrag || !draggingId || draggingId === overId) return
    e.preventDefault()  // autorise le drop
    e.dataTransfer.dropEffect = 'move'
    if (dragOverId !== overId) setDragOverId(overId)
  }
  const handleDragLeave = () => setDragOverId(null)
  const handleDrop = (e: React.DragEvent, targetId: string) => {
    e.preventDefault()
    if (!canDrag || !draggingId || draggingId === targetId) {
      setDraggingId(null); setDragOverId(null); return
    }
    const fromIdx = items.findIndex((x) => x.id === draggingId)
    const toIdx = items.findIndex((x) => x.id === targetId)
    if (fromIdx < 0 || toIdx < 0) {
      setDraggingId(null); setDragOverId(null); return
    }
    const next = [...items]
    const [moved] = next.splice(fromIdx, 1)
    next.splice(toIdx, 0, moved)
    setLocalItems(next)
    setDraggingId(null); setDragOverId(null)
    reorder.mutate(next.map((x) => x.id))
  }
  const handleDragEnd = () => { setDraggingId(null); setDragOverId(null) }

  return (
    <div>
      {/* Header : raccourcis + chip statut */}
      <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {!locked && (
            <PremiumButton
              size="sm"
              onClick={() => { setEditingItem(null); setAddModalOpen(true) }}
              iconLeft={<Plus size={13} />}
            >
              Ajouter un point
            </PremiumButton>
          )}
          {/* Réutiliser l'ODJ — uniquement réunion d'une série + agenda non locké */}
          {!locked && seriesId && (
            <PremiumButton
              variant="secondary"
              size="sm"
              onClick={() => copyFromPrevious.mutate()}
              loading={copyFromPrevious.isPending}
              iconLeft={<ClipboardList size={13} />}
              title="Reporte les points pending/postponed de la séance précédente."
            >
              Reprendre la séance précédente
            </PremiumButton>
          )}
        </div>
        {agenda?.is_validated
          ? <span className="chip-success">Validé</span>
          : <span className="chip-quiet">Brouillon</span>}
      </div>

      <ul className="divide-y divide-border">
        {items.length === 0 && (
          <li className="text-fg-subtle text-sm py-3 text-center">
            Aucun point à l'ordre du jour.
            {!locked && (
              <>
                <br />
                <span className="text-2xs">
                  Cliquez sur « Ajouter un point » {seriesId ? "ou « Reprendre la séance précédente »" : ""} pour démarrer.
                </span>
              </>
            )}
          </li>
        )}
        {items.map((it, i) => {
          const isDragging = draggingId === it.id
          const isDropTarget = dragOverId === it.id && draggingId && draggingId !== it.id
          return (
            <li
              key={it.id}
              className={cn(
                'py-3 first:pt-0 transition-all duration-150',
                isDragging && 'opacity-40',
                isDropTarget && 'border-t-2 border-copper-500',
              )}
              draggable={canDrag}
              onDragStart={(e) => handleDragStart(e, it.id)}
              onDragOver={(e) => handleDragOver(e, it.id)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, it.id)}
              onDragEnd={handleDragEnd}
            >
              <div className="flex items-start gap-3 group">
                {/* Drag handle — visible uniquement si édition autorisée */}
                {canDrag && (
                  <span
                    aria-label="Déplacer ce point"
                    className="text-fg-subtle hover:text-fg cursor-grab active:cursor-grabbing select-none mt-1 opacity-0 group-hover:opacity-100 transition"
                  >
                    <GripVertical size={14} />
                  </span>
                )}
                <span className="text-fg-subtle font-mono text-2xs tabular w-5 mt-1">
                  {(i + 1).toString().padStart(2, '0')}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm">{it.title}</div>
                  <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-1 flex items-center gap-2 flex-wrap">
                    <span>{it.estimated_duration_minutes} min</span>
                    <span>·</span>
                    <span>{it.priority}</span>
                    {it.responsible_detail && <><span>·</span><span>{it.responsible_detail.full_name}</span></>}
                    {it.status === 'postponed' && <><span>·</span><span className="text-amber-400">Reporté</span></>}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {it.status === 'discussed' && (
                    <span className="chip-success text-2xs">Traité</span>
                  )}
                  {it.status !== 'discussed' && status === 'in_progress' && (
                    <button
                      onClick={() => { setDiscussingItem(it.id); setNotes(it.discussion_notes_md ?? '') }}
                      className="text-2xs text-copper-400 hover:text-copper-500 px-2 py-1"
                    >
                      Discuter ↗
                    </button>
                  )}
                  {!locked && (
                    <>
                      <button
                        type="button"
                        onClick={() => { setEditingItem(it); setAddModalOpen(true) }}
                        className="p-1 rounded text-fg-muted hover:text-fg hover:bg-fg/5 opacity-0 group-hover:opacity-100 transition"
                        aria-label="Modifier ce point"
                        title="Modifier"
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (confirm(`Supprimer le point « ${it.title} » ?`)) {
                            deleteItem.mutate(it.id)
                          }
                        }}
                        className="p-1 rounded text-fg-muted hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition"
                        aria-label="Supprimer ce point"
                        title="Supprimer"
                      >
                        <Trash2 size={13} />
                      </button>
                    </>
                  )}
                </div>
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
          )
        })}
      </ul>

      {agenda && !agenda.is_validated && items.length > 0 && (
        <div className="mt-5 pt-5 border-t border-border">
          <PremiumButton variant="secondary" size="sm" onClick={() => validate.mutate()} loading={validate.isPending}>
            <CheckCircle2 size={14} /> Valider l'ordre du jour
          </PremiumButton>
        </div>
      )}

      {/* Modal d'ajout / édition — réutilisable. */}
      <AddAgendaItemModal
        open={addModalOpen}
        onClose={() => { setAddModalOpen(false); setEditingItem(null) }}
        agendaId={agendaId ?? null}
        editingItem={editingItem}
      />
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


/* ═══════════════════════════════════════════════════════════════════
   Modal d'édition de la réunion — appelle PATCH /meetings/{id}/
   ═══════════════════════════════════════════════════════════════════ */

interface EditMeetingForm {
  title: string
  description: string
  meeting_type: string
  scheduled_start: string  // datetime-local format
  scheduled_end: string
  location: string
  video_url: string
  quorum_min: number
  chair: string | null
  secretary: string | null
}

/**
 * Convertit ISO 8601 (`2026-06-15T14:00:00Z`) → format input[type=datetime-local]
 * (`2026-06-15T14:00`). Tronque proprement à la minute, en heure locale.
 */
function isoToLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
       + `T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function EditMeetingModal({
  open, onClose, meeting,
}: { open: boolean; onClose: () => void; meeting: any }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<EditMeetingForm>(() => ({
    title: meeting?.title ?? '',
    description: meeting?.description ?? '',
    meeting_type: meeting?.meeting_type ?? 'regular',
    scheduled_start: isoToLocalInput(meeting?.scheduled_start),
    scheduled_end: isoToLocalInput(meeting?.scheduled_end),
    location: meeting?.location ?? '',
    video_url: meeting?.video_url ?? '',
    quorum_min: meeting?.quorum_min ?? 0,
    chair: (meeting?.chair?.id ?? meeting?.chair) ?? null,
    secretary: (meeting?.secretary?.id ?? meeting?.secretary) ?? null,
  }))

  // Re-synchronise le form si on ouvre le modal sur une nouvelle réunion.
  // (utile en navigation entre 2 réunions sans démontage de la page)
  useEffect(() => {
    if (open && meeting) {
      setForm({
        title: meeting.title ?? '',
        description: meeting.description ?? '',
        meeting_type: meeting.meeting_type ?? 'regular',
        scheduled_start: isoToLocalInput(meeting.scheduled_start),
        scheduled_end: isoToLocalInput(meeting.scheduled_end),
        location: meeting.location ?? '',
        video_url: meeting.video_url ?? '',
        quorum_min: meeting.quorum_min ?? 0,
        chair: (meeting.chair?.id ?? meeting.chair) ?? null,
        secretary: (meeting.secretary?.id ?? meeting.secretary) ?? null,
      })
    }
  }, [open, meeting])

  const save = useMutation({
    mutationFn: async () => {
      // Convertit datetime-local → ISO 8601 (avec timezone locale).
      const payload: any = {
        title: form.title.trim(),
        description: form.description,
        meeting_type: form.meeting_type,
        location: form.location,
        video_url: form.video_url,
        quorum_min: form.quorum_min,
        chair: form.chair,
        secretary: form.secretary,
      }
      if (form.scheduled_start) {
        payload.scheduled_start = new Date(form.scheduled_start).toISOString()
      }
      if (form.scheduled_end) {
        payload.scheduled_end = new Date(form.scheduled_end).toISOString()
      }
      return meetingsApi.update(meeting.id, payload)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: meetingsKeys.detail(meeting.id) })
      qc.invalidateQueries({ queryKey: meetingsKeys.all })
      toast.success('Réunion mise à jour')
      onClose()
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail
        ?? e?.response?.data?.title?.[0]
        ?? 'Mise à jour refusée'),
  })

  const canSave = !!form.title.trim() && !!form.scheduled_start && !!form.scheduled_end
  const datesValid = !form.scheduled_start || !form.scheduled_end
    || (new Date(form.scheduled_end) > new Date(form.scheduled_start))

  return (
    <Modal open={open} onClose={onClose} title="Modifier la réunion">
      <div className="space-y-4">
        <div>
          <label className="label">Titre <span className="text-red-400">*</span></label>
          <input
            className="input"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="CODIR Kaydan — Semaine 23"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Type</label>
            <select
              className="input"
              value={form.meeting_type}
              onChange={(e) => setForm({ ...form, meeting_type: e.target.value })}
            >
              <option value="regular">Ordinaire</option>
              <option value="extraordinary">Extraordinaire</option>
              <option value="strategic">Stratégique</option>
              <option value="crisis">De crise</option>
            </select>
          </div>
          <div>
            <label className="label">Quorum minimum</label>
            <input
              type="number" min={0}
              className="input"
              value={form.quorum_min}
              onChange={(e) => setForm({ ...form, quorum_min: parseInt(e.target.value) || 0 })}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Début <span className="text-red-400">*</span></label>
            <input
              type="datetime-local"
              className="input"
              value={form.scheduled_start}
              onChange={(e) => setForm({ ...form, scheduled_start: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Fin <span className="text-red-400">*</span></label>
            <input
              type="datetime-local"
              className="input"
              value={form.scheduled_end}
              onChange={(e) => setForm({ ...form, scheduled_end: e.target.value })}
            />
          </div>
        </div>
        {!datesValid && (
          <div className="text-2xs text-red-400">
            La date de fin doit être postérieure à la date de début.
          </div>
        )}

        <div>
          <label className="label">Lieu</label>
          <input
            className="input"
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            placeholder="Salle Comex / Visio"
          />
        </div>

        <div>
          <label className="label">Lien visio</label>
          <input
            type="url"
            className="input"
            value={form.video_url}
            onChange={(e) => setForm({ ...form, video_url: e.target.value })}
            placeholder="https://teams.microsoft.com/..."
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Président de séance</label>
            <UserSelect
              value={form.chair as any}
              onChange={(u) => setForm({ ...form, chair: (u as any)?.id ?? u ?? null })}
              placeholder="Choisir…"
            />
          </div>
          <div>
            <label className="label">Secrétaire</label>
            <UserSelect
              value={form.secretary as any}
              onChange={(u) => setForm({ ...form, secretary: (u as any)?.id ?? u ?? null })}
              placeholder="Choisir…"
            />
          </div>
        </div>

        <div>
          <label className="label">Description</label>
          <textarea
            className="input min-h-[90px]"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Objectifs de la réunion, contexte…"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <PremiumButton variant="ghost" onClick={onClose}>Annuler</PremiumButton>
          <PremiumButton
            disabled={!canSave || !datesValid || save.isPending}
            loading={save.isPending}
            onClick={() => save.mutate()}
          >
            Enregistrer
          </PremiumButton>
        </div>
      </div>
    </Modal>
  )
}


/* ═══════════════════════════════════════════════════════════════════
   Modal d'ajout rapide d'un point à l'ordre du jour
   ═══════════════════════════════════════════════════════════════════ */

interface AddAgendaItemForm {
  title: string
  priority: string
  estimated_duration_minutes: number
  responsible: string | null
  description_md: string
}

function AddAgendaItemModal({
  open, onClose, agendaId, editingItem,
}: {
  open: boolean
  onClose: () => void
  agendaId: string | null
  /** Si fourni : le modal passe en mode édition (PATCH). */
  editingItem?: any | null
}) {
  const qc = useQueryClient()
  const isEditMode = !!editingItem

  const [form, setForm] = useState<AddAgendaItemForm>({
    title: '',
    priority: 'medium',
    estimated_duration_minutes: 15,
    responsible: null,
    description_md: '',
  })

  // À chaque ouverture, on (ré)hydrate le form selon le mode.
  useEffect(() => {
    if (!open) return
    if (editingItem) {
      setForm({
        title: editingItem.title ?? '',
        priority: editingItem.priority ?? 'medium',
        estimated_duration_minutes: editingItem.estimated_duration_minutes ?? 15,
        responsible: (editingItem.responsible_detail?.id ?? editingItem.responsible) ?? null,
        description_md: editingItem.description_md ?? '',
      })
    } else {
      setForm({
        title: '', priority: 'medium', estimated_duration_minutes: 15,
        responsible: null, description_md: '',
      })
    }
  }, [open, editingItem])

  const save = useMutation({
    mutationFn: () => {
      const payload: any = {
        title: form.title.trim(),
        priority: form.priority,
        estimated_duration_minutes: form.estimated_duration_minutes,
        description_md: form.description_md,
        responsible: form.responsible,  // null pour désassocier
      }
      if (isEditMode) {
        return agendasApi.updateItem(editingItem.id, payload)
      }
      if (!agendaId) throw new Error('Aucun agenda lié à la réunion.')
      return agendasApi.addItem(agendaId, payload)
    },
    onSuccess: () => {
      if (agendaId) qc.invalidateQueries({ queryKey: agendasKeys.detail(agendaId) })
      toast.success(isEditMode ? 'Point modifié' : "Point ajouté à l'ordre du jour")
      onClose()
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail
        ?? e?.response?.data?.title?.[0]
        ?? (isEditMode ? 'Modification refusée' : 'Ajout refusé')),
  })

  return (
    <Modal
      open={open} onClose={onClose}
      title={isEditMode ? "Modifier le point" : "Ajouter un point à l'ordre du jour"}
    >
      <div className="space-y-4">
        <div>
          <label className="label">Titre du sujet <span className="text-red-400">*</span></label>
          <input
            className="input"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Validation du budget Q3"
            autoFocus
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Priorité</label>
            <select
              className="input"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
            >
              <option value="low">Faible</option>
              <option value="medium">Moyenne</option>
              <option value="high">Élevée</option>
              <option value="critical">Critique</option>
            </select>
          </div>
          <div>
            <label className="label">Durée estimée (min)</label>
            <input
              type="number" min={5} step={5}
              className="input"
              value={form.estimated_duration_minutes}
              onChange={(e) => setForm({
                ...form,
                estimated_duration_minutes: parseInt(e.target.value) || 15,
              })}
            />
          </div>
        </div>

        <div>
          <label className="label">Porteur du sujet</label>
          <UserSelect
            value={form.responsible as any}
            onChange={(u) => setForm({ ...form, responsible: (u as any)?.id ?? u ?? null })}
            placeholder="Optionnel — qui présente ce point ?"
          />
        </div>

        <div>
          <label className="label">Notes / Description</label>
          <textarea
            className="input min-h-[80px]"
            value={form.description_md}
            onChange={(e) => setForm({ ...form, description_md: e.target.value })}
            placeholder="Contexte, documents à préparer, objectifs…"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <PremiumButton variant="ghost" onClick={onClose}>Annuler</PremiumButton>
          <PremiumButton
            disabled={!form.title.trim() || save.isPending || (!isEditMode && !agendaId)}
            loading={save.isPending}
            onClick={() => save.mutate()}
            iconLeft={isEditMode ? <CheckCircle2 size={14} /> : <Plus size={14} />}
          >
            {isEditMode ? 'Enregistrer les modifications' : 'Ajouter le point'}
          </PremiumButton>
        </div>
      </div>
    </Modal>
  )
}
