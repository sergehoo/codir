// Page Résumé IA + Transcription finale + Validation décisions / actions.
import { Link, useParams } from '@tanstack/react-router'
import { ChevronLeft, FileText, ListChecks, Loader2, Mic, Scale } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { cn } from '@/utils/cn'

import { AISummaryPanel } from '../components/AISummaryPanel'
import { CommitmentsPanel } from '../components/CommitmentsPanel'
import { ExtractedActionsPanel } from '../components/ExtractedActionsPanel'
import { ExtractedDecisionsPanel } from '../components/ExtractedDecisionsPanel'
import { RecordingStatusBadge } from '../components/RecordingStatusBadge'
import { SmartAudioPlayer } from '../components/SmartAudioPlayer'
import { TranscriptViewer } from '../components/TranscriptViewer'
import { useExtractions, useRecordingDetail, useRecordingExtraction } from '../hooks/useRecordingExtraction'
import { useRecordingStatus } from '../hooks/useRecordingStatus'

type Tab = 'summary' | 'decisions' | 'actions' | 'transcript'

export function RecordingSummaryPage() {
  const params = useParams({ strict: false }) as { meetingId: string; recordingId: string }
  const { meetingId, recordingId } = params

  const rec = useRecordingDetail(recordingId)
  const status = useRecordingStatus(recordingId, { intervalMs: 4000 })
  const extractions = useExtractions(recordingId)
  const extr = useRecordingExtraction(recordingId)

  const [tab, setTab] = useState<Tab>('summary')

  // ⚠ Lot HIST — refetch du CR quand le pipeline se termine.
  //
  // La génération/régénération est asynchrone (Celery). Le polling /status/
  // s'arrête dès que le statut devient terminal, mais la query `detail` (qui
  // porte summary + ai_minutes) reste sur son cache : l'utilisateur voyait
  // l'ancien compte rendu jusqu'à un rechargement manuel de la page.
  // On détecte la transition "en cours → terminé" et on refetch.
  const wasProcessingRef = useRef(false)
  const liveStatus = status.data?.status
  useEffect(() => {
    if (!liveStatus) return
    const processing = [
      'summarizing', 'extracting_actions',
      'generating_final_transcript', 'transcribing',
    ].includes(liveStatus)

    if (processing) {
      wasProcessingRef.current = true
    } else if (wasProcessingRef.current) {
      // Transition terminée → on récupère le CR fraîchement généré.
      wasProcessingRef.current = false
      rec.refetch()
      extractions.refetch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveStatus])

  if (rec.isLoading) {
    return (
      <div className="p-10 grid place-items-center">
        <Loader2 size={24} className="animate-spin text-copper-500" />
      </div>
    )
  }
  if (!rec.data) {
    return (
      <div className="p-10 text-center text-sm text-fg-muted">Enregistrement introuvable.</div>
    )
  }

  const data = rec.data
  const currentStatus = status.data?.status ?? data.status
  const isProcessing = ['summarizing', 'extracting_actions',
    'generating_final_transcript', 'transcribing'].includes(currentStatus)

  const tabs: { id: Tab; label: string; icon: any; count?: number }[] = [
    { id: 'summary', label: 'Résumé', icon: FileText },
    {
      id: 'decisions', label: 'Décisions', icon: Scale,
      count: extractions.data?.filter((e) => e.extraction_type === 'decision').length,
    },
    {
      id: 'actions', label: 'Actions', icon: ListChecks,
      count: extractions.data?.filter((e) => e.extraction_type === 'action').length,
    },
    { id: 'transcript', label: 'Transcription', icon: Mic },
  ]

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <Link
        to="/meetings/$id"
        params={{ id: meetingId }}
        className="inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg transition"
      >
        <ChevronLeft size={14} /> Retour à la réunion
      </Link>

      <header className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="serif text-2xl font-semibold">Compte rendu IA</h1>
          <p className="text-sm text-fg-muted mt-1">{data.title}</p>
        </div>
        <RecordingStatusBadge status={currentStatus} />
      </header>

      {isProcessing && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg border border-copper-500/30 bg-copper-500/5 text-sm">
          <Loader2 size={14} className="animate-spin text-copper-500" />
          Traitement IA en cours… cette page se rafraîchit automatiquement.
        </div>
      )}

      {/* Lecteur audio complet — si on a l'URL de l'audio brut */}
      {data.audio_url && (
        <SmartAudioPlayer
          url={data.audio_url}
          label="Audio complet de la réunion"
        />
      )}

      {/* Tabs */}
      <nav className="flex items-center gap-1 border-b border-border">
        {tabs.map((t) => {
          const active = tab === t.id
          const Icon = t.icon
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition',
                active
                  ? 'border-copper-500 text-fg'
                  : 'border-transparent text-fg-muted hover:text-fg',
              )}
            >
              <Icon size={14} /> {t.label}
              {typeof t.count === 'number' && t.count > 0 && (
                <span className="text-2xs px-1.5 py-0.5 rounded-full bg-fg/10 text-fg-muted">
                  {t.count}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {tab === 'summary' && (
        <div className="space-y-6">
          <AISummaryPanel
            recordingId={recordingId}
            meetingId={meetingId}
            summary={data.summary ?? ''}
            minutes={data.ai_minutes}
            onRegenerate={() => extr.regenerateSummary()}
            onMinutesUpdated={() => rec.refetch()}
            isRegenerating={extr.isRegenerating}
          />
          {/* Lot 5 — Engagements oraux détectés */}
          <CommitmentsPanel recordingId={recordingId} />
        </div>
      )}

      {tab === 'decisions' && (
        <ExtractedDecisionsPanel
          extractions={extractions.data ?? []}
          onCreate={async (ids) => { await extr.createDecisions(ids) }}
          isCreating={extr.isCreatingDecisions}
        />
      )}

      {tab === 'actions' && (
        <ExtractedActionsPanel
          extractions={extractions.data ?? []}
          onCreate={async (ids) => { await extr.createActionPlans(ids) }}
          isCreating={extr.isCreatingActions}
        />
      )}

      {tab === 'transcript' && (
        <TranscriptViewer segments={data.transcript_final ?? []} />
      )}
    </div>
  )
}
