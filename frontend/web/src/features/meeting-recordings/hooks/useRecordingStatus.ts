// Hook de polling de statut — utilisé pendant le pipeline async backend.
// Le polling s'arrête automatiquement quand status atteint un état terminal
// (completed / failed / waiting_speaker_mapping).
import { useQuery } from '@tanstack/react-query'

import { recordingsApi } from '../api'
import type { RecordingStatusPayload, RecordingStatus } from '../types/recording.types'

const TERMINAL: RecordingStatus[] = ['completed', 'failed', 'waiting_speaker_mapping']

export function useRecordingStatus(recordingId: string | null | undefined, opts?: { intervalMs?: number }) {
  const intervalMs = opts?.intervalMs ?? 3000

  return useQuery<RecordingStatusPayload>({
    queryKey: ['recording', 'status', recordingId],
    queryFn: () => recordingsApi.status(recordingId!),
    enabled: !!recordingId,
    refetchInterval: (q) => {
      const data = q.state.data as RecordingStatusPayload | undefined
      if (!data) return intervalMs
      return TERMINAL.includes(data.status) ? false : intervalMs
    },
    refetchOnWindowFocus: false,
    staleTime: 0,
  })
}
