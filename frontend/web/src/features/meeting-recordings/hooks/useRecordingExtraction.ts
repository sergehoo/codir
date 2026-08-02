// useRecordingExtraction — liste les extractions IA + push validations.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { recordingsApi } from '../api'
import type {
  AIExtractionType, RecordingAIExtraction,
} from '../types/recording.types'

export function useExtractions(
  recordingId: string | undefined | null,
  type?: AIExtractionType,
) {
  return useQuery<RecordingAIExtraction[]>({
    queryKey: ['recording', 'extractions', recordingId, type ?? 'all'],
    queryFn: () => recordingsApi.listExtractions(recordingId!, type),
    enabled: !!recordingId,
    staleTime: 15_000,
  })
}

export function useRecordingExtraction(recordingId: string) {
  const qc = useQueryClient()

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['recording', 'extractions', recordingId] })
    qc.invalidateQueries({ queryKey: ['recording', 'detail', recordingId] })
  }

  const createDecisions = useMutation({
    mutationFn: (extractionIds: string[]) =>
      recordingsApi.createDecisions(recordingId, extractionIds),
    onSuccess: invalidate,
  })

  const createActionPlans = useMutation({
    mutationFn: (extractionIds: string[]) =>
      recordingsApi.createActionPlans(recordingId, extractionIds),
    onSuccess: invalidate,
  })

  const regenerateSummary = useMutation({
    mutationFn: () => recordingsApi.generateSummary(recordingId),
    onSuccess: () => {
      // ⚠ La génération est asynchrone (Celery) : au moment où cette mutation
      // répond, le nouveau CR n'existe pas encore. On invalide quand même le
      // detail pour ne pas rester sur un cache figé — et le composant
      // RecordingSummaryPage refetch en plus quand le statut redevient
      // terminal (voir useEffect sur status). Sans cette double sécurité,
      // l'utilisateur voyait l'ancien CR jusqu'à un rechargement manuel.
      qc.invalidateQueries({ queryKey: ['recording', 'status', recordingId] })
      qc.invalidateQueries({ queryKey: ['recording', 'detail', recordingId] })
      qc.invalidateQueries({ queryKey: ['recording', 'minutes-versions', recordingId] })
    },
  })

  return {
    createDecisions: createDecisions.mutateAsync,
    createActionPlans: createActionPlans.mutateAsync,
    regenerateSummary: regenerateSummary.mutateAsync,
    isCreatingDecisions: createDecisions.isPending,
    isCreatingActions: createActionPlans.isPending,
    isRegenerating: regenerateSummary.isPending,
    error: (createDecisions.error || createActionPlans.error
      || regenerateSummary.error) as Error | null,
  }
}

export function useRecordingDetail(recordingId: string | undefined | null) {
  return useQuery({
    queryKey: ['recording', 'detail', recordingId],
    queryFn: () => recordingsApi.retrieve(recordingId!),
    enabled: !!recordingId,
    staleTime: 10_000,
  })
}
