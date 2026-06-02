import { apiClient } from '@/api/client'
import type { Agenda, AgendaItem } from '@/types'

export const agendasApi = {
  retrieve: async (id: string) => (await apiClient.get<Agenda>(`/agendas/${id}/`)).data,
  validate: async (id: string) => (await apiClient.post<Agenda>(`/agendas/${id}/validate/`)).data,
  reorder: async (id: string, ordered_ids: string[]) =>
    (await apiClient.post<Agenda>(`/agendas/${id}/reorder/`, { ordered_ids })).data,
  addItem: async (id: string, payload: Partial<AgendaItem>) =>
    (await apiClient.post<AgendaItem>(`/agendas/${id}/items/`, payload)).data,
  updateItem: async (id: string, payload: Partial<AgendaItem>) =>
    (await apiClient.patch<AgendaItem>(`/agendas/items/${id}/`, payload)).data,
  deleteItem: async (id: string) => (await apiClient.delete(`/agendas/items/${id}/`)).data,
  discussItem: async (id: string, notes_md?: string) =>
    (await apiClient.post<AgendaItem>(`/agendas/items/${id}/discuss/`, { notes_md })).data,
  postponeItem: async (id: string, reason?: string) =>
    (await apiClient.post<AgendaItem>(`/agendas/items/${id}/postpone/`, { reason })).data,

  /**
   * Reporte les items non-clôturés de la séance précédente d'une série.
   * Renvoie { copied, source_meeting_id, source_meeting_title, agenda }.
   */
  copyFromPrevious: async (id: string) =>
    (await apiClient.post<{
      copied: number
      source_meeting_id: string | null
      source_meeting_title: string
      agenda: Agenda
    }>(`/agendas/${id}/copy-from-previous/`)).data,
}

export const agendasKeys = {
  detail: (id: string) => ['agenda', id] as const,
  item: (id: string) => ['agenda-item', id] as const,
}
