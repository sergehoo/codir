import { apiClient } from '@/api/client'
import type { Meeting, MeetingAttendance, MeetingParticipant, Paginated } from '@/types'

export type MeetingFilters = {
  status?: string
  from_date?: string
  to_date?: string
  search?: string
}

export const meetingsApi = {
  list: async (filters: MeetingFilters = {}) =>
    (await apiClient.get<Paginated<Meeting>>('/meetings/', { params: filters })).data,
  retrieve: async (id: string) =>
    (await apiClient.get<Meeting>(`/meetings/${id}/`)).data,
  create: async (payload: Partial<Meeting>) =>
    (await apiClient.post<Meeting>('/meetings/', payload)).data,
  update: async (id: string, payload: Partial<Meeting>) =>
    (await apiClient.patch<Meeting>(`/meetings/${id}/`, payload)).data,
  remove: async (id: string) =>
    (await apiClient.delete(`/meetings/${id}/`)).data,

  // ─── Transitions ────────────────────────────────────────
  schedule: async (id: string) => (await apiClient.post<Meeting>(`/meetings/${id}/schedule/`)).data,
  start:    async (id: string) => (await apiClient.post<Meeting>(`/meetings/${id}/start/`)).data,
  complete: async (id: string) => (await apiClient.post<Meeting>(`/meetings/${id}/complete/`)).data,
  cancel:   async (id: string, reason?: string) =>
    (await apiClient.post<Meeting>(`/meetings/${id}/cancel/`, { reason })).data,

  // ─── Participants ───────────────────────────────────────
  listParticipants: async (id: string) =>
    (await apiClient.get<MeetingParticipant[]>(`/meetings/${id}/participants/`)).data,
  addParticipant: async (id: string, payload: Partial<MeetingParticipant>) =>
    (await apiClient.post<MeetingParticipant>(`/meetings/${id}/participants/`, payload)).data,
  removeParticipant: async (participantId: string) =>
    (await apiClient.delete(`/meetings/participants/${participantId}/`)).data,

  // ─── Attendance ─────────────────────────────────────────
  listAttendance: async (id: string) =>
    (await apiClient.get<MeetingAttendance[]>(`/meetings/${id}/attendance/`)).data,
  recordAttendance: async (
    id: string,
    payload: { participant: string; status: string; arrived_at?: string },
  ) =>
    (await apiClient.post<MeetingAttendance>(`/meetings/${id}/attendance/`, payload)).data,

  // ─── Minutes / PV ───────────────────────────────────────
  minutes: async (id: string) => (await apiClient.get(`/meetings/${id}/minutes/`)).data,

  // ─── Smart notes (Tiptap) ───────────────────────────────
  smartNotes: async (id: string): Promise<SmartNotesResponse> =>
    (await apiClient.get(`/meetings/${id}/smart-notes/`)).data,
  autosaveNotes: async (id: string, payload: { content_json: object; content_md?: string }) =>
    (await apiClient.post(`/meetings/${id}/notes/autosave/`, payload)).data,
  parseNotes: async (id: string): Promise<SmartNotesResponse> =>
    (await apiClient.post(`/meetings/${id}/parse-notes/`)).data,
  generateDecisions: async (id: string) =>
    (await apiClient.post(`/meetings/${id}/generate-decisions/`)).data,
  publishDecision: async (id: string, ddId: string) =>
    (await apiClient.post(`/meetings/${id}/detected-decisions/${ddId}/publish/`)).data,
  publishAction: async (id: string, daId: string) =>
    (await apiClient.post(`/meetings/${id}/detected-actions/${daId}/publish/`)).data,
  dismissDecision: async (id: string, ddId: string) =>
    (await apiClient.post(`/meetings/${id}/detected-decisions/${ddId}/dismiss/`)).data,
  mentionCandidates: async (id: string, q?: string): Promise<MentionCandidate[]> =>
    (await apiClient.get(`/meetings/${id}/mention-candidates/`, { params: q ? { q } : {} })).data,
}

export type MentionCandidate = {
  id: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  avatar?: string
  is_executive?: boolean
}

export type DetectedAction = {
  id: string
  title: string
  raw_line: string
  assignee: string | null
  assignee_detail?: MentionCandidate
  assignee_mention: string
  order: number
  status: 'pending' | 'published' | 'dismissed'
  action_task?: string | null
  detected_decision?: string | null
  published_at?: string | null
}

export type DetectedDecision = {
  id: string
  title: string
  raw_line: string
  order: number
  status: 'pending' | 'published' | 'dismissed'
  decision?: string | null
  published_at?: string | null
  actions: DetectedAction[]
}

export type MeetingNoteMention = {
  id: string
  raw_text: string
  user: string | null
  user_detail?: MentionCandidate
  occurrences: number
}

export type SmartNotesResponse = {
  note: {
    id: string
    content_json: any
    content_md: string
    version: number
    last_autosaved_at: string | null
  } | null
  detected_decisions: DetectedDecision[]
  orphan_actions: DetectedAction[]
  mentions: MeetingNoteMention[]
}

export const meetingsKeys = {
  all: ['meetings'] as const,
  list: (f: MeetingFilters) => [...meetingsKeys.all, 'list', f] as const,
  detail: (id: string) => [...meetingsKeys.all, 'detail', id] as const,
  smartNotes: (id: string) => [...meetingsKeys.all, id, 'smart-notes'] as const,
  mentions: (id: string, q?: string) => [...meetingsKeys.all, id, 'mentions', q ?? ''] as const,
  participants: (id: string) => [...meetingsKeys.detail(id), 'participants'] as const,
  attendance: (id: string) => [...meetingsKeys.detail(id), 'attendance'] as const,
  minutes: (id: string) => [...meetingsKeys.detail(id), 'minutes'] as const,
}
