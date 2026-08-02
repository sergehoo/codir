/**
 * Hooks d'historisation des enregistrements et comptes rendus (lot HIST).
 *
 *   - useMeetingRecordingsHistory : tous les takes d'une réunion
 *   - useMinutesVersions          : historique des versions du CR
 *   - useRecordingActions         : restaurer / archiver / renommer / supprimer
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { recordingsApi } from '../api'
import type {
  MeetingRecording, MinutesVersionsResponse,
} from '../types/recording.types'

/** Liste enrichie de tous les enregistrements d'une réunion. */
export function useMeetingRecordingsHistory(
  meetingId: string | undefined | null,
  opts: { includeArchived?: boolean } = {},
) {
  return useQuery<MeetingRecording[]>({
    queryKey: ['recordings', 'history', meetingId, opts.includeArchived ?? false],
    queryFn: () => recordingsApi.listHistoryForMeeting(meetingId!, {
      includeArchived: opts.includeArchived,
      limit: 100,
    }),
    enabled: !!meetingId,
    staleTime: 15_000,
  })
}

/** Historique des versions du compte rendu d'un enregistrement. */
export function useMinutesVersions(
  recordingId: string | undefined | null,
  enabled = true,
) {
  return useQuery<MinutesVersionsResponse>({
    queryKey: ['recording', 'minutes-versions', recordingId],
    queryFn: () => recordingsApi.minutesVersions(recordingId!),
    enabled: !!recordingId && enabled,
    staleTime: 10_000,
  })
}

/**
 * Mutations sur un enregistrement : restauration de version, archivage,
 * renommage, suppression.
 *
 * `meetingId` sert à invalider la liste d'historique de la réunion parente
 * après une action qui la modifie (archivage, suppression, renommage).
 */
export function useRecordingActions(
  recordingId: string,
  meetingId?: string | null,
) {
  const qc = useQueryClient()

  const invalidateRecording = () => {
    qc.invalidateQueries({ queryKey: ['recording', 'detail', recordingId] })
    qc.invalidateQueries({ queryKey: ['recording', 'minutes-versions', recordingId] })
  }

  const invalidateLists = () => {
    // Les deux clés de liste utilisées dans l'app.
    qc.invalidateQueries({ queryKey: ['recordings', 'history'] })
    if (meetingId) {
      qc.invalidateQueries({ queryKey: ['recordings', 'list', meetingId] })
    }
  }

  const restoreVersion = useMutation({
    mutationFn: (versionId: string) =>
      recordingsApi.restoreMinutesVersion(recordingId, versionId),
    onSuccess: () => {
      invalidateRecording()
      invalidateLists()
    },
  })

  const rename = useMutation({
    mutationFn: (payload: { title?: string; internal_note?: string }) =>
      recordingsApi.updateMeta(recordingId, payload),
    onSuccess: () => {
      invalidateRecording()
      invalidateLists()
    },
  })

  const setArchived = useMutation({
    mutationFn: (archived: boolean) => recordingsApi.archive(recordingId, archived),
    onSuccess: () => {
      invalidateRecording()
      invalidateLists()
    },
  })

  const remove = useMutation({
    mutationFn: () => recordingsApi.remove(recordingId),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ['recording', 'detail', recordingId] })
      qc.removeQueries({ queryKey: ['recording', 'minutes-versions', recordingId] })
      invalidateLists()
    },
  })

  return {
    restoreVersion: restoreVersion.mutateAsync,
    rename: rename.mutateAsync,
    setArchived: setArchived.mutateAsync,
    remove: remove.mutateAsync,
    isRestoring: restoreVersion.isPending,
    isRenaming: rename.isPending,
    isArchiving: setArchived.isPending,
    isRemoving: remove.isPending,
    error: (restoreVersion.error || rename.error || setArchived.error
      || remove.error) as Error | null,
  }
}
