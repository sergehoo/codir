// useSpeakerMapping — gère la liste des speakers détectés + mutations de mapping.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { recordingsApi } from '../api'
import type { DetectedSpeaker, SpeakerMappingInput } from '../types/recording.types'

export function useSpeakers(recordingId: string | undefined | null) {
  return useQuery<DetectedSpeaker[]>({
    queryKey: ['recording', 'speakers', recordingId],
    queryFn: () => recordingsApi.speakers(recordingId!),
    enabled: !!recordingId,
    staleTime: 30_000,
  })
}

export function useSpeakerMapping(recordingId: string) {
  const qc = useQueryClient()

  const mapMutation = useMutation({
    mutationFn: (mappings: SpeakerMappingInput[]) =>
      recordingsApi.setSpeakerMapping(recordingId, mappings),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recording', 'speakers', recordingId] })
      qc.invalidateQueries({ queryKey: ['recording', 'detail', recordingId] })
    },
  })

  const confirmMutation = useMutation({
    mutationFn: () => recordingsApi.confirmSpeakers(recordingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recording', 'speakers', recordingId] })
      qc.invalidateQueries({ queryKey: ['recording', 'status', recordingId] })
      qc.invalidateQueries({ queryKey: ['recording', 'detail', recordingId] })
    },
  })

  return {
    setMappings: mapMutation.mutateAsync,
    confirm: confirmMutation.mutateAsync,
    isSaving: mapMutation.isPending || confirmMutation.isPending,
    error: (mapMutation.error || confirmMutation.error) as Error | null,
  }
}
