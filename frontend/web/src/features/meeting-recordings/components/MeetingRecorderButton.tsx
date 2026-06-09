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
import {
  AlertTriangle, CheckCircle2, FileText, Loader2, Mic, Sparkles, Upload, Users,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { cn } from '@/utils/cn'

import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { useRecordingStatus } from '../hooks/useRecordingStatus'
import { useRecordingUpload } from '../hooks/useRecordingUpload'
import type { MeetingRecording, RecordingStatus } from '../types/recording.types'

import { AudioPermissionAlert } from './AudioPermissionAlert'
import { FileUploadCard } from './FileUploadCard'
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
  // Mode "idle" : laisse choisir entre capter le micro ou téléverser un fichier.
  const [inputMode, setInputMode] = useState<'record' | 'upload'>('record')
  // ⚡ Skip diarisation : si coché, le pipeline saute la détection des voix
  // ET l'étape d'identification utilisateur → CR généré direct, ~2-3× plus vite.
  // Default OFF pour préserver la qualité (diarisation = attribution par speaker).
  const [skipSpeakerDetection, setSkipSpeakerDetection] = useState(false)
  // Si l'upload échoue, on garde le Blob audio en mémoire pour permettre un retry
  // sans re-enregistrer la réunion (l'audio capturé est précieux).
  const [savedBlob, setSavedBlob] = useState<Blob | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

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

  const doUpload = async (blob: Blob) => {
    setPhase('uploading')
    setUploadError(null)
    try {
      const created = await upload.upload({
        blob,
        recordingId: recording?.id,
        durationSeconds: mr.durationMs / 1000,
        consentAcknowledged: consentAck,
        skipSpeakerDetection,
      })
      setRecording(created)
      onRecordingCreated?.(created)
      setSavedBlob(null)
      setPhase('processing')
    } catch (err: any) {
      // Garde l'audio en mémoire pour permettre un retry.
      // Récupère le message backend détaillé (502 → cause storage exacte).
      setSavedBlob(blob)
      const data = err?.response?.data
      const msg = data?.detail
        ?? (typeof data === 'string' ? data : null)
        ?? err?.message
        ?? "Erreur réseau inconnue."
      setUploadError(msg)
      toast.error("Échec de l'envoi de l'audio", {
        description: msg.length > 300 ? msg.slice(0, 300) + '…' : msg,
        duration: 10000,
      })
      setPhase('uploading')  // reste en uploading pour montrer le retry
    }
  }

  const handleStop = async () => {
    const blob = await mr.stop()
    if (!blob) return
    await doUpload(blob)
  }

  /** Upload depuis un fichier externe (FileUploadCard). */
  const handleFileUpload = async (file: File, durationSeconds?: number) => {
    setPhase('uploading')
    setUploadError(null)
    try {
      // Titre : on tronque à 240 chars (max_length backend = 250) et on retire
      // l'extension pour avoir un titre lisible côté UI.
      const baseName = file.name.replace(/\.[^/.]+$/, '').trim()
      const title = (baseName || 'Audio importé').slice(0, 240)

      const created = await upload.upload({
        blob: file,
        recordingId: recording?.id,
        durationSeconds,
        consentAcknowledged: consentAck,
        skipSpeakerDetection,
        title,
      } as any)  // upload accepte Blob ; File hérite de Blob
      setRecording(created)
      onRecordingCreated?.(created)
      setSavedBlob(null)
      setPhase('processing')
    } catch (err: any) {
      // Garde le fichier pour permettre un retry depuis l'UI d'erreur.
      setSavedBlob(file)
      const data = err?.response?.data
      // Récupère le message le plus précis possible :
      // 1. detail (erreur globale)
      // 2. première erreur de champ (ex: audio[0])
      // 3. message JS
      let msg = data?.detail
      if (!msg && data && typeof data === 'object') {
        for (const [field, errs] of Object.entries(data)) {
          if (Array.isArray(errs) && errs.length) {
            msg = `${field} : ${errs[0]}`
            break
          }
        }
      }
      msg = msg
        ?? (typeof data === 'string' ? data : null)
        ?? err?.message
        ?? "Erreur réseau inconnue."
      setUploadError(msg)
      toast.error("Échec de l'envoi du fichier", {
        description: msg.length > 300 ? msg.slice(0, 300) + '…' : msg,
        duration: 10000,
      })
      setPhase('uploading')
    }
  }

  const handleRetryUpload = () => {
    if (savedBlob) doUpload(savedBlob)
  }

  // ─── Render ─────────────────────────────────────────────

  if (phase === 'idle') {
    return (
      <div className="space-y-3">
        <div className="flex items-start gap-3 p-4 rounded-xl border border-copper-500/30 bg-copper-500/5">
          <Sparkles size={20} className="text-copper-500 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold">Compte rendu IA de la réunion</div>
            <p className="text-xs text-fg-muted mt-1">{CONSENT_TEXT}</p>
            <label className="flex items-center gap-2 mt-3 cursor-pointer text-xs text-fg"
                   htmlFor={`consent-ack-${meetingId}`}>
              <input
                id={`consent-ack-${meetingId}`}
                name="consent_acknowledged"
                type="checkbox"
                checked={consentAck}
                onChange={(e) => setConsentAck(e.target.checked)}
                className="rounded border-border accent-copper-500"
              />
              J'ai informé les participants. J'assume la responsabilité de cet enregistrement.
            </label>
          </div>
        </div>

        {/* ─── Option vitesse : skip détection des voix ─── */}
        <label
          htmlFor={`skip-speakers-${meetingId}`}
          className="flex items-start gap-2.5 p-3 rounded-lg border border-border bg-bg-elevated cursor-pointer hover:border-copper-500/30 transition"
        >
          <input
            id={`skip-speakers-${meetingId}`}
            name="skip_speaker_detection"
            type="checkbox"
            checked={skipSpeakerDetection}
            onChange={(e) => setSkipSpeakerDetection(e.target.checked)}
            className="rounded border-border accent-copper-500 mt-0.5"
          />
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-fg flex items-center gap-1.5">
              ⚡ Mode rapide — passer la détection des voix
            </div>
            <p className="text-2xs text-fg-muted mt-0.5 leading-relaxed">
              {skipSpeakerDetection
                ? "Le CR sera généré ~2-3× plus vite, sans attribution par locuteur (texte brut)."
                : "Décoche si tu veux gagner du temps : le CR sera prêt directement, sans étape d'identification des voix."}
            </p>
          </div>
        </label>

        {/* ─── Toggle : Enregistrer en direct OU Téléverser un fichier ─── */}
        <div className="grid grid-cols-2 gap-1.5 p-1 rounded-xl bg-bg-base border border-border">
          <button
            type="button"
            onClick={() => setInputMode('record')}
            className={cn(
              'inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition',
              inputMode === 'record'
                ? 'bg-copper-500 text-white shadow-sm'
                : 'text-fg-muted hover:text-fg hover:bg-fg/5',
            )}
          >
            <Mic size={13} /> Enregistrer en direct
          </button>
          <button
            type="button"
            onClick={() => setInputMode('upload')}
            className={cn(
              'inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition',
              inputMode === 'upload'
                ? 'bg-copper-500 text-white shadow-sm'
                : 'text-fg-muted hover:text-fg hover:bg-fg/5',
            )}
          >
            <Upload size={13} /> Téléverser un fichier
          </button>
        </div>

        {/* ─── Mode "Enregistrer en direct" ─── */}
        {inputMode === 'record' && (
          <>
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
            {!consentAck && (
              <p className="text-2xs text-fg-subtle text-center">
                Cochez la case de consentement pour activer le bouton.
              </p>
            )}
          </>
        )}

        {/* ─── Mode "Téléverser un fichier" ─── */}
        {inputMode === 'upload' && (
          <>
            <FileUploadCard
              consentAck={consentAck}
              isUploading={upload.isUploading}
              onUpload={handleFileUpload}
            />
            {!consentAck && (
              <p className="text-2xs text-fg-subtle text-center">
                Cochez la case de consentement pour activer l'envoi.
              </p>
            )}
          </>
        )}
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
    // Cas 1 : erreur d'upload → affiche le message backend + bouton retry.
    if (uploadError && savedBlob) {
      return (
        <div className="p-5 rounded-xl border border-red-500/30 bg-red-500/5 space-y-4">
          <div className="flex items-start gap-3">
            <AlertTriangle size={20} className="text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-red-300">
                L'envoi de l'audio a échoué
              </div>
              <p className="text-xs text-red-200/80 mt-1 break-words">{uploadError}</p>
              <p className="text-2xs text-fg-muted mt-2">
                Votre audio est conservé en mémoire — vous pouvez retenter
                l'envoi sans réenregistrer la réunion.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleRetryUpload}
              disabled={upload.isUploading}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-copper-500 hover:bg-copper-600 disabled:bg-fg/20 text-white text-sm font-semibold transition"
            >
              {upload.isUploading
                ? <><Loader2 size={14} className="animate-spin" /> Nouvelle tentative…</>
                : <><Sparkles size={14} /> Réessayer l'envoi</>}
            </button>
            <a
              href={URL.createObjectURL(savedBlob)}
              download={`reunion-${meetingId}-${Date.now()}.webm`}
              className="text-xs text-fg-muted hover:text-fg underline"
            >
              Télécharger l'audio localement
            </a>
          </div>
        </div>
      )
    }
    // Cas 2 : upload en cours normal
    return (
      <div className="p-5 rounded-xl border border-border bg-bg-elevated space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Loader2 size={16} className="animate-spin text-copper-500" />
            Envoi de l'audio au serveur…
          </div>
          {upload.chunkInfo && (
            <span className="text-2xs uppercase tracking-wider text-copper-400 font-semibold">
              Chunk {upload.chunkInfo.current} / {upload.chunkInfo.total}
            </span>
          )}
        </div>
        <RecordingUploadProgress percent={upload.progress} />
        <p className="text-xs text-fg-muted">
          {upload.chunkInfo
            ? "Upload chunked en cours — 4 chunks envoyés en parallèle. La reprise est automatique en cas de coupure."
            : "Ne fermez pas cette page. L'enregistrement sera transcrit automatiquement dès que l'upload sera terminé."}
        </p>
      </div>
    )
  }

  // phase === 'processing' or 'done'
  const status: RecordingStatus | undefined = statusQuery.data?.status ?? recording?.status
  if (!status) return null

  return (
    <PipelinePanel
      status={status}
      meetingId={meetingId}
      recordingId={recording?.id}
      errorMessage={statusQuery.data?.error_message || recording?.error_message}
      speakersCount={statusQuery.data?.speakers_count ?? 0}
      hasDecisions={statusQuery.data?.has_decisions_drafts ?? false}
      hasActions={statusQuery.data?.has_actions_drafts ?? false}
      stepLabel={statusQuery.data?.step_label}
      stepProgress={statusQuery.data?.step_progress}
      overallProgress={statusQuery.data?.overall_progress}
      etaSeconds={statusQuery.data?.eta_seconds ?? null}
    />
  )
}


/* ════════════════════════════════════════════════════════════
   PipelinePanel : étapes visuelles du traitement IA
   ════════════════════════════════════════════════════════════ */

interface PipelinePanelProps {
  status: RecordingStatus
  meetingId: string
  recordingId?: string
  errorMessage?: string
  speakersCount?: number
  hasDecisions?: boolean
  hasActions?: boolean
  stepLabel?: string
  stepProgress?: number
  overallProgress?: number
  etaSeconds?: number | null
}

// Ordre des étapes du pipeline (sert pour l'UI étape par étape)
const PIPELINE_STEPS: { key: RecordingStatus[]; label: string; icon: any }[] = [
  { key: ['uploading', 'uploaded', 'processing'], label: 'Préparation audio', icon: Sparkles },
  { key: ['transcribing'], label: 'Transcription', icon: FileText },
  { key: ['diarizing'], label: 'Détection des voix', icon: Users },
  { key: ['waiting_speaker_mapping'], label: 'Identification (vous)', icon: Users },
  { key: ['generating_final_transcript'], label: 'Transcript final', icon: FileText },
  { key: ['summarizing'], label: 'Résumé IA', icon: Sparkles },
  { key: ['extracting_actions'], label: 'Extraction décisions/actions', icon: CheckCircle2 },
  { key: ['completed'], label: 'Terminé', icon: CheckCircle2 },
]

function statusToStepIndex(status: RecordingStatus): number {
  for (let i = 0; i < PIPELINE_STEPS.length; i++) {
    if (PIPELINE_STEPS[i].key.includes(status)) return i
  }
  return 0
}

function PipelinePanel({
  status, meetingId, recordingId, errorMessage,
  speakersCount = 0, hasDecisions = false, hasActions = false,
  stepLabel, stepProgress, overallProgress, etaSeconds,
}: PipelinePanelProps) {
  const currentIdx = statusToStepIndex(status)
  const isFailed = status === 'failed'
  const isWaitingUser = status === 'waiting_speaker_mapping'
  const isDone = status === 'completed'

  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-bg-elevated to-bg-base shadow-sm">
      {/* Subtle ambient glow tant qu'on traite */}
      {!isDone && !isFailed && (
        <div
          aria-hidden
          className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-32 bg-copper-500/10 blur-3xl pointer-events-none"
        />
      )}

      <div className="relative p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Sparkles size={16} className="text-copper-500" />
            <span className="text-sm font-semibold tracking-wide">
              Pipeline IA — Compte rendu automatique
            </span>
          </div>
          <RecordingStatusBadge status={status} />
        </div>

        {/* ─── Progression globale + ETA ─── */}
        {!isFailed && !isDone && !isWaitingUser && (stepLabel || typeof overallProgress === 'number') && (
          <div className="space-y-2.5 p-3 rounded-lg bg-bg-base border border-border">
            <div className="flex items-center justify-between gap-3 text-xs">
              <div className="font-semibold text-fg">
                {stepLabel || 'En cours…'}
                {typeof stepProgress === 'number' && (
                  <span className="ml-2 text-copper-400 tabular-nums">{stepProgress}%</span>
                )}
              </div>
              {etaSeconds !== null && etaSeconds !== undefined && etaSeconds > 0 && (
                <div className="text-2xs uppercase tracking-wider text-fg-muted">
                  ~ {formatEta(etaSeconds)} restantes
                </div>
              )}
            </div>
            {/* Barre étape courante */}
            <div className="h-1.5 bg-bg-elevated rounded-full overflow-hidden">
              <div
                className="h-full bg-copper-500 transition-all duration-700 ease-out"
                style={{ width: `${stepProgress ?? 0}%` }}
              />
            </div>
            {/* Barre overall */}
            {typeof overallProgress === 'number' && (
              <div className="flex items-center gap-2 mt-1">
                <div className="text-2xs uppercase tracking-wider text-fg-subtle min-w-[60px]">
                  Global
                </div>
                <div className="flex-1 h-1 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500/70 transition-all duration-700 ease-out"
                    style={{ width: `${overallProgress}%` }}
                  />
                </div>
                <div className="text-2xs text-fg-muted tabular-nums min-w-[35px] text-right">
                  {overallProgress}%
                </div>
              </div>
            )}
          </div>
        )}

        {/* Erreur explicite */}
        {isFailed && (
          <div className="p-3.5 rounded-lg border border-red-500/30 bg-red-500/10 text-red-200 text-xs">
            <div className="font-semibold mb-1">Échec du traitement</div>
            <div className="opacity-90">{errorMessage || "Erreur inconnue — consultez les logs serveur."}</div>
          </div>
        )}

        {/* Stepper visuel — pas d'étape passée si failed */}
        {!isFailed && (
          <ol className="space-y-2.5">
            {PIPELINE_STEPS.map((step, idx) => {
              const isPast = idx < currentIdx
              const isCurrent = idx === currentIdx
              const Icon = step.icon
              return (
                <li
                  key={idx}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-300",
                    isPast && "opacity-70",
                    isCurrent && "bg-copper-500/10 border border-copper-500/30",
                  )}
                >
                  <span className={cn(
                    "w-7 h-7 rounded-full grid place-items-center shrink-0",
                    isPast ? "bg-emerald-500/15 text-emerald-400"
                      : isCurrent ? "bg-copper-500 text-white"
                      : "bg-fg/10 text-fg-subtle",
                  )}>
                    {isPast
                      ? <CheckCircle2 size={14} />
                      : isCurrent
                        ? (isWaitingUser ? <Users size={14} /> : <Loader2 size={14} className="animate-spin" />)
                        : <Icon size={13} />}
                  </span>
                  <span className={cn(
                    "text-sm",
                    isPast && "text-fg-muted",
                    isCurrent && "font-semibold text-fg",
                    !isPast && !isCurrent && "text-fg-subtle",
                  )}>
                    {step.label}
                  </span>
                  {isCurrent && !isWaitingUser && (
                    <span className="ml-auto text-2xs text-copper-400 tracking-widest uppercase font-semibold">
                      En cours…
                    </span>
                  )}
                </li>
              )
            })}
          </ol>
        )}

        {/* Stats live quand on a déjà des données */}
        {(speakersCount > 0 || hasDecisions || hasActions) && (
          <div className="grid grid-cols-3 gap-2 text-center text-2xs">
            <div className="p-2.5 rounded-lg bg-bg-base border border-border">
              <div className="text-xl font-semibold text-copper-400 tabular-nums">{speakersCount}</div>
              <div className="text-fg-subtle uppercase tracking-wider mt-0.5">Voix détectées</div>
            </div>
            <div className="p-2.5 rounded-lg bg-bg-base border border-border">
              <div className="text-xl font-semibold text-copper-400 tabular-nums">{hasDecisions ? '✓' : '–'}</div>
              <div className="text-fg-subtle uppercase tracking-wider mt-0.5">Décisions</div>
            </div>
            <div className="p-2.5 rounded-lg bg-bg-base border border-border">
              <div className="text-xl font-semibold text-copper-400 tabular-nums">{hasActions ? '✓' : '–'}</div>
              <div className="text-fg-subtle uppercase tracking-wider mt-0.5">Actions</div>
            </div>
          </div>
        )}

        {/* CTA contextuels */}
        {isWaitingUser && recordingId && (
          <Link
            to="/meetings/$meetingId/recordings/$recordingId/speakers"
            params={{ meetingId, recordingId }}
            className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl bg-gradient-to-br from-copper-500 to-copper-600 hover:from-copper-600 hover:to-copper-700 text-white text-sm font-semibold shadow-md shadow-copper-500/30 transition-all duration-200"
          >
            <Users size={15} /> Identifier les voix détectées →
          </Link>
        )}

        {isDone && recordingId && (
          <div className="grid grid-cols-2 gap-2">
            <Link
              to="/meetings/$meetingId/recordings/$recordingId/summary"
              params={{ meetingId, recordingId }}
              className="flex items-center justify-center gap-2 px-3.5 py-2.5 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white text-sm font-semibold shadow-md shadow-emerald-500/20 transition-all duration-200"
            >
              <FileText size={14} /> Voir le CR
            </Link>
            <Link
              to="/meetings/$meetingId/recordings/$recordingId/speakers"
              params={{ meetingId, recordingId }}
              className="flex items-center justify-center gap-2 px-3.5 py-2.5 rounded-xl border border-border bg-bg-base hover:bg-fg/5 text-sm font-medium transition-all duration-200"
            >
              <CheckCircle2 size={14} /> Voix
            </Link>
          </div>
        )}

        {/* Info discrète */}
        {!isFailed && !isWaitingUser && !isDone && (
          <p className="text-2xs text-fg-subtle text-center">
            Vous pouvez fermer cette page — le traitement continue côté serveur
            et vous serez notifié par email.
          </p>
        )}
      </div>
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

/** Format ETA en français : "5min", "1h 12min", "45s". */
function formatEta(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) {
    const restSec = Math.round(seconds % 60)
    return restSec ? `${minutes}min ${restSec}s` : `${minutes}min`
  }
  const hours = Math.floor(minutes / 60)
  const restMin = minutes % 60
  return restMin ? `${hours}h ${restMin}min` : `${hours}h`
}
