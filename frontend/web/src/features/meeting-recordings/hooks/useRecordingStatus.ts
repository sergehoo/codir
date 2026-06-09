// Hook de polling de statut — utilisé pendant le pipeline async backend.
// Le polling s'arrête automatiquement quand status atteint un état terminal
// (completed / failed / waiting_speaker_mapping).
//
// Stratégie de polling ADAPTATIVE :
//   - Étapes courtes (upload, processing, diarizing, summarizing) → 2s
//   - Étapes longues (transcribing surtout) → 5s (AAI prend ~1× durée audio)
//   - Refetch chaque changement d'état pour avoir step_progress à jour
import { useQuery } from '@tanstack/react-query'

import { recordingsApi } from '../api'
import type { RecordingStatusPayload, RecordingStatus } from '../types/recording.types'

const TERMINAL: RecordingStatus[] = ['completed', 'failed', 'waiting_speaker_mapping']

// Polling rapide pour les étapes qui se terminent vite (UI doit suivre)
const FAST_POLL: RecordingStatus[] = [
  'uploading', 'uploaded', 'processing', 'diarizing',
  'generating_final_transcript', 'summarizing', 'extracting_actions',
]
// Polling lent : transcription qui peut durer 5-15 min sur 1h+ audio
const SLOW_POLL: RecordingStatus[] = ['transcribing']

export function useRecordingStatus(recordingId: string | null | undefined, opts?: { intervalMs?: number }) {
  const defaultMs = opts?.intervalMs ?? 3000

  return useQuery<RecordingStatusPayload>({
    queryKey: ['recording', 'status', recordingId],
    queryFn: () => recordingsApi.status(recordingId!),
    enabled: !!recordingId,
    refetchInterval: (q) => {
      const data = q.state.data as RecordingStatusPayload | undefined
      if (!data) return defaultMs
      if (TERMINAL.includes(data.status)) return false
      if (SLOW_POLL.includes(data.status)) return 5000  // AAI lent : 5s suffit
      if (FAST_POLL.includes(data.status)) return 2000  // Étape courte : 2s
      return defaultMs
    },
    refetchOnWindowFocus: false,
    staleTime: 0,
  })
}
