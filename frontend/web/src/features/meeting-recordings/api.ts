// API client meeting_recordings — wrappers axios typés.
import { apiClient } from '@/api/client'

import { ChunkedUploader, type ChunkedUploaderOptions } from './chunkedUploader'
import type {
  DetectedSpeaker, MeetingRecording, RecordingAIExtraction,
  RecordingCommitment,
  RecordingStatusPayload, SpeakerMappingInput, SpeakerSegment,
} from './types/recording.types'

/**
 * Seuil de bascule single-shot → chunked.
 *
 * En dessous : un seul POST multipart (simple, latence faible).
 * Au-dessus : on découpe en chunks de 50 Mo, 4 en parallèle, retry par chunk.
 *
 * Calé sur 50 Mo : couvre un audio ~25 min @ 256 kbps. Au-delà, le chunked
 * est plus fiable (résiste aux coupures, retry granulaire).
 */
export const CHUNKED_UPLOAD_THRESHOLD = 50 * 1024 * 1024

export const recordingsApi = {
  // ─── Nested under meeting ────────────────────────────────
  listForMeeting: async (meetingId: string) =>
    (await apiClient.get<MeetingRecording[]>(`/meetings/${meetingId}/recordings/`)).data,

  start: async (meetingId: string, payload: { title?: string; consent_acknowledged?: boolean }) =>
    (await apiClient.post<MeetingRecording>(
      `/meetings/${meetingId}/recordings/start/`, payload,
    )).data,

  /**
   * Upload chunked (≥ 50 Mo) ou single-shot (< 50 Mo).
   *
   * Bascule automatique selon la taille du Blob :
   *   - < 50 Mo : un seul POST multipart classique
   *   - ≥ 50 Mo : pipeline chunked (init → N×PUT en parallèle → complete)
   */
  uploadAuto: async (
    meetingId: string,
    audioBlob: Blob,
    opts: Omit<ChunkedUploaderOptions, 'blob' | 'meetingId' | 'filename'> & {
      recordingId?: string  // ignoré en chunked (le serveur crée son propre rec)
      title?: string
      durationSeconds?: number
      consentAcknowledged?: boolean
      skipSpeakerDetection?: boolean
      onProgress?: (percent: number) => void
    } = {},
  ): Promise<MeetingRecording> => {
    const filename = audioBlob.type.includes('webm') ? 'recording.webm'
      : audioBlob.type.includes('ogg') ? 'recording.ogg'
      : audioBlob.type.includes('mp4') ? 'recording.m4a'
      : 'recording.audio'

    if (audioBlob.size < CHUNKED_UPLOAD_THRESHOLD) {
      // Path court : on délègue à upload() (compatible existant)
      return recordingsApi.upload(meetingId, audioBlob, opts)
    }

    // Chunked
    const uploader = new ChunkedUploader({
      blob: audioBlob,
      meetingId,
      filename,
      contentType: audioBlob.type,
      title: opts.title,
      durationSeconds: opts.durationSeconds,
      consentAcknowledged: opts.consentAcknowledged,
      skipSpeakerDetection: opts.skipSpeakerDetection,
      onProgress: opts.onProgress,
      onChunkComplete: opts.onChunkComplete,
      abortSignal: opts.abortSignal,
    })
    return uploader.run()
  },

  /** Upload du Blob audio en multipart single-shot (cas legacy / petits fichiers). */
  upload: async (
    meetingId: string,
    audioBlob: Blob,
    opts: {
      recordingId?: string
      title?: string
      durationSeconds?: number
      consentAcknowledged?: boolean
      skipSpeakerDetection?: boolean
      onProgress?: (percent: number) => void
    } = {},
  ) => {
    const form = new FormData()
    if (opts.recordingId) form.append('recording_id', opts.recordingId)
    if (opts.title) form.append('title', opts.title)
    if (opts.durationSeconds != null) form.append('duration_seconds', String(opts.durationSeconds))
    form.append('consent_acknowledged', String(opts.consentAcknowledged ?? false))
    form.append('skip_speaker_detection', String(opts.skipSpeakerDetection ?? false))
    // Extension cohérente avec le type MIME — important pour AssemblyAI.
    const filename = audioBlob.type.includes('webm') ? 'recording.webm'
      : audioBlob.type.includes('ogg') ? 'recording.ogg'
      : audioBlob.type.includes('mp4') ? 'recording.m4a'
      : 'recording.audio'
    form.append('audio', new File([audioBlob], filename, { type: audioBlob.type }))
    const res = await apiClient.post<MeetingRecording>(
      `/meetings/${meetingId}/recordings/upload/`,
      form,
      {
        // ⚠ Notre apiClient a un défaut `Content-Type: application/json`.
        // Si on ne le neutralise pas explicitement, axios sérialise le
        // FormData en JSON et le File devient `{}` → 400 backend ("audio
        // is required"). On passe Content-Type=undefined pour qu'axios
        // détecte FormData et génère lui-même `multipart/form-data;
        // boundary=...` correctement.
        headers: { 'Content-Type': undefined as unknown as string },
        // 10 min : autorise les uploads > 1h d'enregistrement sur connexions
        // lentes. Aligné sur proxy_read_timeout nginx (600s) et gunicorn timeout.
        timeout: 10 * 60 * 1000,
        onUploadProgress: (e) => {
          if (opts.onProgress && e.total) {
            opts.onProgress(Math.round((e.loaded / e.total) * 100))
          }
        },
      },
    )
    return res.data
  },

  // ─── Flat under /recordings/ ─────────────────────────────
  retrieve: async (id: string) =>
    (await apiClient.get<MeetingRecording>(`/recordings/${id}/`)).data,

  status: async (id: string) =>
    (await apiClient.get<RecordingStatusPayload>(`/recordings/${id}/status/`)).data,

  process: async (id: string) =>
    (await apiClient.post(`/recordings/${id}/process/`)).data,

  speakers: async (id: string) =>
    (await apiClient.get<DetectedSpeaker[]>(`/recordings/${id}/speakers/`)).data,

  segments: async (id: string) =>
    (await apiClient.get<SpeakerSegment[]>(`/recordings/${id}/segments/`)).data,

  setSpeakerMapping: async (id: string, mappings: SpeakerMappingInput[]) =>
    (await apiClient.post<{ updated: DetectedSpeaker[] }>(
      `/recordings/${id}/speaker-mapping/`, { mappings },
    )).data,

  confirmSpeakers: async (id: string) =>
    (await apiClient.post(`/recordings/${id}/confirm-speakers/`)).data,

  generateFinalTranscript: async (id: string) =>
    (await apiClient.post(`/recordings/${id}/generate-final-transcript/`)).data,

  generateSummary: async (id: string) =>
    (await apiClient.post(`/recordings/${id}/generate-summary/`)).data,

  extractDecisions: async (id: string) =>
    (await apiClient.post(`/recordings/${id}/extract-decisions/`)).data,

  extractActions: async (id: string) =>
    (await apiClient.post(`/recordings/${id}/extract-actions/`)).data,

  // Lot 5 — Engagements oraux détectés
  commitments: async (id: string) =>
    (await apiClient.get<{ count: number; results: RecordingCommitment[] }>(
      `/recordings/${id}/commitments/`,
    )).data,

  listExtractions: async (id: string, type?: string) =>
    (await apiClient.get<RecordingAIExtraction[]>(
      `/recordings/${id}/extractions/`, { params: type ? { type } : {} },
    )).data,

  createDecisions: async (id: string, extractionIds: string[]) =>
    (await apiClient.post<{ created: Array<{ extraction_id: string; decision_id?: string; error?: string }> }>(
      `/recordings/${id}/create-decisions/`, { extraction_ids: extractionIds },
    )).data,

  createActionPlans: async (id: string, extractionIds: string[]) =>
    (await apiClient.post<{ created: Array<{ extraction_id: string; action_plan_id?: string; error?: string }> }>(
      `/recordings/${id}/create-action-plans/`, { extraction_ids: extractionIds },
    )).data,

  /** Met à jour le résumé + minutes (édition manuelle avant export). */
  updateMinutes: async (id: string, payload: { summary?: string; ai_minutes?: string }) =>
    (await apiClient.patch<MeetingRecording>(
      `/recordings/${id}/minutes/`, payload,
    )).data,

  /** Téléchargement DOCX (déclenche directement le download navigateur). */
  exportDocxUrl: (id: string) => `/api/v1/recordings/${id}/export/docx/`,

  /** Téléchargement PDF (déclenche directement le download navigateur). */
  exportPdfUrl: (id: string) => `/api/v1/recordings/${id}/export/pdf/`,

  /**
   * Téléchargement direct du fichier (DOCX ou PDF) via axios pour conserver
   * l'auth Bearer. Retourne un Blob qu'on peut transformer en download.
   */
  exportDocxBlob: async (id: string) =>
    (await apiClient.get(`/recordings/${id}/export/docx/`, {
      responseType: 'blob',
    })).data as Blob,
  exportPdfBlob: async (id: string) =>
    (await apiClient.get(`/recordings/${id}/export/pdf/`, {
      responseType: 'blob',
    })).data as Blob,
}
