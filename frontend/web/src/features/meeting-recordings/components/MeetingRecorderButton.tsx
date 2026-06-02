// Composant principal d'enregistrement à inclure dans MeetingDetailPage.
//
// Workflow :
// 1. État initial : bouton "Démarrer l'enregistrement" + avertissement consentement.
// 2. Pendant l'enregistrement : RecordingControlPanel (pause/reprendre/arrêter).
// 3. Sur arrêt : upload du Blob → recordingsApi.upload() → polling status.
// 4. Quand status = waiting_speaker_mapping : lien vers la page Identification des voix.
// 5. Quand status = completed : lien vers Résumé / Décisions / Actions.
//
// Le composant gère lui-même le consentement : on ne déclenche getUserMedia
// QU'APRÈS que l'utilisateur ait validé la bannière "Réunion enregistrée".
import { Link } from '@tanstack/react-router'
import { CheckCircle2, FileText, Loader2, Mic, Sparkles, Users } from 'lucide-react'
import { useEffect, useState } from 'react'

import { cn } from '@/utils/cn'

import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { useRecordingStatus } from '../hooks/useRecordingStatus'
import { useRecordingUpload } from '../hooks/useRecordingUpload'
import type { MeetingRecording, RecordingStatus } from '../types/recording.types'

import { AudioPermissionAlert } from './AudioPermissionAlert'
import { RecordingControlPanel } from './RecordingControlPanel'
import { RecordingStatusBadge } from './RecordingStatusBadge'
import { RecordingUploadProgress } from './RecordingUploadProgress'

interface Props {
  meetingId: string
  /** Recording existant à reprendre (optionnel — sinon on en crée un nouveau). */
  existingRecording?: MeetingRecording | null
  onRecordingCreated?: (rec: MeetingRecording) => void
}

const CONSENT_TEXT = (
  "Cette réunion va être enregistrée à des fins de compte rendu IA. "
  + "Les participants doivent être informés avant le début de l'enregistrement."
)

export function MeetingRecorderButton({
  meetingId, existingRecording, onRecordingCreated,
}: Props) {
  const [consentAck, setConsentAck] = useState(false)
  const [recording, setRecording] = useState<MeetingRecording | null>(existingRecording ?? null)
  const [phase, setPhase] = useState<'idle' | 'capturing' | 'uploading' | 'processing' | 'done'>(
    existingRecording ? statusToPhase(existingRecording.status) : 'idle',
  )

  const mr = useMediaRecorder({ preventUnload: true })
  const upload = useRecordingUpload(meetingId)
  const statusQuery = useRecordingStatus(recording?.id, { intervalMs: 3000 })

  // Synchronise la phase quand le statut backend change
  useEffect(() => {
    const s = statusQuery.data?.status
    if (!s) return
    setPhase(statusToPhase(s))
  }, [statusQuery.data?.status])

  const handleStart = async () => {
    if (!consentAck) return
    const ok = await mr.start()
    if (!ok) return
    setPhase('capturing')
  }

  const handleStop = async () => {
    const blob = await mr.stop()
    if (!blob) return
    setPhase('uploading')
    try {
      const created = await upload.upload({
        blob,
        recordingId: recording?.id,
        durationSeconds: mr.durationMs / 1000,
        consentAcknowledged: consentAck,
      })
      setRecording(created)
      onRecordingCreated?.(created)
      setPhase('processing')
    } catch (e) {
      // Conserve l'audio en local pour ne pas perdre la prise — l'utilisateur peut retry
      setPhase('capturing')
    }
  }

  // ─── Render ─────────────────────────────────────────────

  if (phase === 'idle') {
    return (
      <div className="space-y-3">
        <div className="flex items-start gap-3 p-4 rounded-xl border border-copper-500/30 bg-copper-500/5">
          <Sparkles size={20} className="text-copper-500 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold">Enregistrement IA de la réunion</div>
            <p className="text-xs text-fg-muted mt-1">{CONSENT_TEXT}</p>
            <label className="flex items-center gap-2 mt-3 cursor-pointer text-xs text-fg">
              <input
                type="checkbox"
                checked={consentAck}
                onChange={(e) => setConsentAck(e.target.checked)}
                className="rounded border-border accent-copper-500"
              />
              J'ai informé les participants. J'assume la responsabilité de cet enregistrement.
            </label>
          </div>
        </div>

        {mr.permissionError && (
          <AudioPermissionAlert
            message={mr.permissionError}
            onRetry={() => { mr.reset(); setConsentAck(consentAck) }}
          />
        )}

        <button
          type="button"
          disabled={!consentAck}
          onClick={handleStart}
          className={cn(
            'w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl',
            'text-sm font-semibold transition shadow-sm',
            consentAck
              ? 'bg-copper-500 hover:bg-copper-600 text-white'
              : 'bg-fg/10 text-fg-muted cursor-not-allowed',
          )}
        >
          <Mic size={16} /> Démarrer l'enregistrement
        </button>
      </div>
    )
  }

  if (phase === 'capturing') {
    return (
      <RecordingControlPanel
        state={mr.state}
        durationMs={mr.durationMs}
        audioLevel={mr.audioLevel}
        onPause={mr.pause}
        onResume={mr.resume}
        onStop={handleStop}
      />
    )
  }

  if (phase === 'uploading') {
    return (
      <div className="p-5 rounded-xl border border-border bg-bg-elevated space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Loader2 size={16} className="animate-spin text-copper-500" />
          Envoi de l'audio au serveur…
        </div>
        <RecordingUploadProgress percent={upload.progress} />
        <p className="text-xs text-fg-muted">
          Ne fermez pas cette page. L'enregistrement sera transcrit automatiquement
          dès que l'upload sera terminé.
        </p>
      </div>
    )
  }

  // phase === 'processing' or 'done'
  const status: RecordingStatus | undefined = statusQuery.data?.status ?? recording?.status
  if (!status) return null

  return (
    <div className="p-5 rounded-xl border border-border bg-bg-elevated space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Sparkles size={16} className="text-copper-500" />
          <span className="text-sm font-semibold">Pipeline IA</span>
        </div>
        <RecordingStatusBadge status={status} />
      </div>

      {status === 'failed' && (
        <div className="p-3 rounded-lg bg-red-500/10 text-red-300 text-xs">
          {statusQuery.data?.error_message || recording?.error_message || 'Erreur inconnue'}
        </div>
      )}

      {(status === 'transcribing' || status === 'diarizing'
        || status === 'processing' || status === 'uploaded'
        || status === 'generating_final_transcript' || status === 'summarizing'
        || status === 'extracting_actions') && (
        <div className="flex items-center gap-2 text-xs text-fg-muted">
          <Loader2 size={12} className="animate-spin" />
          Traitement en arrière-plan… vous pouvez fermer cette page.
        </div>
      )}

      {status === 'waiting_speaker_mapping' && recording && (
        <Link
          to="/meetings/$meetingId/recordings/$recordingId/speakers"
          params={{ meetingId, recordingId: recording.id }}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-copper-500 hover:bg-copper-600 text-white text-sm font-semibold transition"
        >
          <Users size={14} /> Identifier les voix détectées
        </Link>
      )}

      {status === 'completed' && recording && (
        <div className="flex flex-wrap gap-2">
          <Link
            to="/meetings/$meetingId/recordings/$recordingId/summary"
            params={{ meetingId, recordingId: recording.id }}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-semibold transition"
          >
            <FileText size={14} /> Voir le compte rendu IA
          </Link>
          <Link
            to="/meetings/$meetingId/recordings/$recordingId/speakers"
            params={{ meetingId, recordingId: recording.id }}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-border bg-bg-base hover:bg-fg/5 text-sm font-medium transition"
          >
            <CheckCircle2 size={14} /> Revoir les voix
          </Link>
        </div>
      )}
    </div>
  )
}

function statusToPhase(status: RecordingStatus): 'idle' | 'capturing' | 'uploading' | 'processing' | 'done' {
  if (status === 'created') return 'idle'
  if (status === 'recording') return 'capturing'
  if (status === 'uploading') return 'uploading'
  if (status === 'completed' || status === 'failed') return 'done'
  return 'processing'
}
