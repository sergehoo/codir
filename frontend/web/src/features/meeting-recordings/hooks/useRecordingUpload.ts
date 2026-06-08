// useRecordingUpload — wrapper TanStack Query autour de recordingsApi.uploadAuto.
//
// Bascule auto :
//   - blob < 50 Mo  → single-shot POST multipart (legacy)
//   - blob ≥ 50 Mo  → chunked upload (4 chunks en parallèle, retry 3x par chunk)
//
// Expose progress 0..100 + chunkInfo {current,total} pour UI détaillée optionnelle.
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { CHUNKED_UPLOAD_THRESHOLD, recordingsApi } from '../api'

export function useRecordingUpload(meetingId: string) {
  const qc = useQueryClient()
  const [progress, setProgress] = useState(0)
  const [chunkInfo, setChunkInfo] = useState<{ current: number; total: number } | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const mutation = useMutation({
    mutationFn: async (vars: {
      blob: Blob
      recordingId?: string
      title?: string
      durationSeconds?: number
      consentAcknowledged?: boolean
    }) => {
      setProgress(0)
      setChunkInfo(null)
      // Fresh AbortController pour cette mutation (réutilisable via .reset)
      abortRef.current?.abort()
      abortRef.current = new AbortController()

      const isChunked = vars.blob.size >= CHUNKED_UPLOAD_THRESHOLD
      return recordingsApi.uploadAuto(meetingId, vars.blob, {
        recordingId: vars.recordingId,
        title: vars.title,
        durationSeconds: vars.durationSeconds,
        consentAcknowledged: vars.consentAcknowledged,
        onProgress: setProgress,
        onChunkComplete: isChunked
          ? (idx, total) => setChunkInfo({ current: idx + 1, total })
          : undefined,
        abortSignal: abortRef.current.signal,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recordings', 'list', meetingId] })
      qc.invalidateQueries({ queryKey: ['meeting', meetingId] })
    },
  })

  return {
    upload: mutation.mutateAsync,
    isUploading: mutation.isPending,
    error: mutation.error as Error | null,
    progress,
    /** Détail chunked (null si single-shot ou pas encore démarré). */
    chunkInfo,
    /** Cancel l'upload en cours (utile bouton "Annuler" UI). */
    abort: () => abortRef.current?.abort(),
    reset: () => {
      setProgress(0)
      setChunkInfo(null)
      abortRef.current?.abort()
      mutation.reset()
    },
  }
}
