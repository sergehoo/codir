// useRecordingUpload — wrapper TanStack Query autour de recordingsApi.upload
// avec gestion percent + invalidation cache.
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { recordingsApi } from '../api'

export function useRecordingUpload(meetingId: string) {
  const qc = useQueryClient()
  const [progress, setProgress] = useState(0)

  const mutation = useMutation({
    mutationFn: async (vars: {
      blob: Blob
      recordingId?: string
      title?: string
      durationSeconds?: number
      consentAcknowledged?: boolean
    }) => {
      setProgress(0)
      return recordingsApi.upload(meetingId, vars.blob, {
        recordingId: vars.recordingId,
        title: vars.title,
        durationSeconds: vars.durationSeconds,
        consentAcknowledged: vars.consentAcknowledged,
        onProgress: setProgress,
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
    reset: () => { setProgress(0); mutation.reset() },
  }
}
