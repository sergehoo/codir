// Types front pour meeting_recordings.
// Reflète strictement le contrat exposé par les serializers DRF.

export type RecordingStatus =
  | 'created'
  | 'recording'
  | 'uploading'
  | 'uploaded'
  | 'processing'
  | 'transcribing'
  | 'diarizing'
  | 'waiting_speaker_mapping'
  | 'generating_final_transcript'
  | 'summarizing'
  | 'extracting_actions'
  | 'completed'
  | 'failed'

export type AIExtractionType =
  | 'summary'
  | 'minutes'
  | 'decision'
  | 'action'
  | 'risk'
  | 'deadline'
  | 'blocker'
  | 'question'

export type AIExtractionStatus = 'draft' | 'validated' | 'rejected' | 'pushed'

export interface UserMini {
  id: string
  email: string
  full_name: string
  first_name?: string
  last_name?: string
}

export interface DetectedSpeaker {
  id: string
  speaker_label: string
  display_name: string
  sample_audio: string | null
  sample_audio_url: string | null
  total_segments: number
  total_duration: number
  confidence: number
  suggested_participant: UserMini | null
  mapped_participant: UserMini | null
  is_confirmed: boolean
  voice_match_confidence: number  // 0..1 cosine similarity au VoiceProfile suggéré
  created_at: string
  updated_at: string
}

export interface SpeakerSegment {
  id: string
  speaker_label: string
  start_time: number
  end_time: number
  text: string
  confidence: number
  audio_excerpt: string | null
}

export interface TranscriptSegmentFinal {
  speaker: string         // display_name (nom réel après mapping)
  speaker_label: string   // SPEAKER_XX original
  start: number
  end: number
  text: string
}

export interface RecordingAIExtraction {
  id: string
  extraction_type: AIExtractionType
  raw_payload: Record<string, any>
  status: AIExtractionStatus
  created_decision: string | null
  created_action_plan: string | null
  validation_status: string
  validated_by: UserMini | null
  validated_at: string | null
  created_at: string
  updated_at: string
}

export interface MeetingRecording {
  id: string
  meeting: string
  title: string
  status: RecordingStatus
  recorded_by: UserMini | null
  duration_seconds: number
  file_size: number
  mime_type: string
  audio_url: string | null
  started_at: string | null
  stopped_at: string | null
  uploaded_at: string | null
  processing_started_at: string | null
  processing_finished_at: string | null
  error_message: string
  created_at: string
  updated_at: string

  // Detail-only
  transcript_raw?: string
  transcript_with_speakers?: Array<{
    speaker: string
    start: number
    end: number
    text: string
    confidence: number
  }>
  transcript_final?: TranscriptSegmentFinal[]
  summary?: string
  ai_minutes?: string
  speakers?: DetectedSpeaker[]
  extractions?: RecordingAIExtraction[]
  segments_count?: number
  consent_acknowledged_at?: string | null
}

export interface RecordingStatusPayload {
  id: string
  status: RecordingStatus
  duration_seconds: number
  speakers_count: number
  segments_count: number
  has_summary: boolean
  has_decisions_drafts: boolean
  has_actions_drafts: boolean
  error_message: string
  // Progression estimée (calculée côté backend)
  step_index?: number          // 1-based
  total_steps?: number
  step_label?: string          // "Transcription", "Détection des voix", etc.
  step_progress?: number       // 0..100 sur l'étape courante
  overall_progress?: number    // 0..100 sur tout le pipeline
  eta_seconds?: number | null  // temps restant estimé sur l'étape (null si bloqué user)
}

export interface SpeakerMappingInput {
  speaker_label: string
  participant_id: string
  notes?: string
}

// ─── Helpers d'affichage ───────────────────────────────────

export const STATUS_LABELS: Record<RecordingStatus, string> = {
  created: 'Créé',
  recording: 'Enregistrement en cours',
  uploading: 'Upload…',
  uploaded: 'Uploadé',
  processing: 'Traitement initial…',
  transcribing: 'Transcription en cours…',
  diarizing: 'Détection des voix…',
  waiting_speaker_mapping: 'Identification des voix requise',
  generating_final_transcript: 'Génération du transcript final…',
  summarizing: 'Résumé IA en cours…',
  extracting_actions: 'Extraction décisions/actions…',
  completed: 'Terminé',
  failed: 'Échec',
}

export const ACTIVE_PROCESSING_STATUSES: RecordingStatus[] = [
  'uploading', 'uploaded', 'processing', 'transcribing', 'diarizing',
  'generating_final_transcript', 'summarizing', 'extracting_actions',
]

export function isProcessing(status: RecordingStatus): boolean {
  return ACTIVE_PROCESSING_STATUSES.includes(status)
}

// Lot 5 — Engagement oral détecté lors d'une réunion
export type CommitmentStatus = 'pending' | 'confirmed' | 'executed' | 'cancelled' | 'failed'

export interface RecordingCommitment {
  id: string
  status: CommitmentStatus
  title: string
  speaker_label: string
  evidence_quote: string
  assignee_email: string
  due_date: string
  created_at: string
  confirmed_at: string
  executed_at: string
  result_object_id: string
  result_object_type: string
  error_message: string
}
