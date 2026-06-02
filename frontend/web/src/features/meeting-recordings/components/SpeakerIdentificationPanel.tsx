// Panel maître pour la page "Identifier les voix détectées".
// Affiche N SpeakerCard + bouton "Confirmer toutes les associations".
import { CheckCircle2, Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { useSpeakerMapping, useSpeakers } from '../hooks/useSpeakerMapping'
import type { DetectedSpeaker, SpeakerMappingInput } from '../types/recording.types'

import { SpeakerCard } from './SpeakerCard'

interface Participant {
  id: string
  full_name: string
  email: string
  role?: string
}

interface Props {
  recordingId: string
  participants: Participant[]
  /** Callback déclenché APRÈS confirmation réussie (utile pour rediriger). */
  onConfirmed?: () => void
}

export function SpeakerIdentificationPanel({
  recordingId, participants, onConfirmed,
}: Props) {
  const speakersQuery = useSpeakers(recordingId)
  const mapping = useSpeakerMapping(recordingId)

  // Sélections locales (pas encore poussées) : { speaker_label → participant_id | null }
  const [draft, setDraft] = useState<Record<string, string | null>>({})

  const speakers = speakersQuery.data ?? []
  const merged: DetectedSpeaker[] = useMemo(() => speakers.map((s) => {
    const localPid = draft[s.speaker_label]
    if (localPid === undefined) return s
    return {
      ...s,
      mapped_participant: localPid
        ? participants.find((p) => p.id === localPid)
            ? ({ id: localPid, email: '', full_name: participants.find((p) => p.id === localPid)!.full_name } as any)
            : null
        : null,
    }
  }), [speakers, draft, participants])

  const allMapped = merged.every((s) => s.mapped_participant?.id)

  const handleChange = (label: string, pid: string | null) => {
    setDraft((prev) => ({ ...prev, [label]: pid }))
  }

  const handleConfirm = async () => {
    // 1. Pousse tous les mappings non-null
    const toSend: SpeakerMappingInput[] = []
    for (const s of merged) {
      const pid = s.mapped_participant?.id ?? null
      if (pid) {
        toSend.push({ speaker_label: s.speaker_label, participant_id: pid })
      }
    }
    if (toSend.length > 0) await mapping.setMappings(toSend)
    // 2. Confirme (bascule WAITING_SPEAKER_MAPPING → GENERATING_FINAL_TRANSCRIPT)
    await mapping.confirm()
    onConfirmed?.()
  }

  if (speakersQuery.isLoading) {
    return (
      <div className="p-8 grid place-items-center">
        <Loader2 size={24} className="animate-spin text-copper-500" />
      </div>
    )
  }
  if (speakers.length === 0) {
    return (
      <div className="p-6 rounded-xl border border-border bg-bg-elevated text-center text-sm text-fg-muted">
        Aucune voix détectée pour cet enregistrement. La transcription est peut-être encore en cours.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-copper-500/30 bg-copper-500/5 text-xs text-fg">
        <p className="font-medium mb-1">Identifiez chaque voix détectée.</p>
        <p className="text-fg-muted">
          Écoutez l'extrait représentatif de chaque voix, puis associez-la à un participant
          de la réunion. Cette identification ne fait <strong>pas</strong> de reconnaissance
          automatique : c'est vous qui validez chaque association.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {merged.map((sp) => (
          <SpeakerCard
            key={sp.id}
            speaker={sp}
            participants={participants}
            onChange={handleChange}
            disabled={mapping.isSaving}
          />
        ))}
      </div>

      <div className="flex items-center justify-between gap-3 p-4 rounded-xl border border-border bg-bg-elevated">
        <div className="text-xs text-fg-muted">
          {allMapped ? (
            <>Toutes les voix sont associées. Vous pouvez générer le compte rendu final.</>
          ) : (
            <>Associez chaque voix à un participant pour activer la suite.</>
          )}
        </div>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={!allMapped || mapping.isSaving}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-copper-500 hover:bg-copper-600 disabled:bg-fg/10 disabled:text-fg-muted disabled:cursor-not-allowed text-white text-sm font-semibold transition"
        >
          {mapping.isSaving
            ? <><Loader2 size={14} className="animate-spin" /> Enregistrement…</>
            : <><CheckCircle2 size={14} /> Confirmer et générer le CR</>}
        </button>
      </div>

      {mapping.error && (
        <div className="p-3 rounded-lg bg-red-500/10 text-red-300 text-xs">
          {mapping.error.message}
        </div>
      )}
    </div>
  )
}
