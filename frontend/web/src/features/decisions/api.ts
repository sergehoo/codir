import { apiClient } from '@/api/client'
import type { ActionPlan, Decision, Paginated } from '@/types'

export type DecisionFilters = {
  status?: string
  priority?: string
  responsible?: string
  meeting?: string
  search?: string
}

export const decisionsApi = {
  list: async (f: DecisionFilters = {}) =>
    (await apiClient.get<Paginated<Decision> | Decision[]>('/decisions/', { params: f })).data,
  myDecisions: async () =>
    (await apiClient.get<Paginated<Decision> | Decision[]>('/decisions/my-decisions/')).data,
  retrieve: async (id: string) =>
    (await apiClient.get<Decision>(`/decisions/${id}/`)).data,
  create: async (payload: Partial<Decision>) =>
    (await apiClient.post<Decision>('/decisions/', payload)).data,
  update: async (id: string, payload: Partial<Decision>) =>
    (await apiClient.patch<Decision>(`/decisions/${id}/`, payload)).data,
  remove: async (id: string) =>
    (await apiClient.delete(`/decisions/${id}/`)).data,

  // Transitions
  approve:  async (id: string) => (await apiClient.post<Decision>(`/decisions/${id}/approve/`)).data,
  start:    async (id: string) => (await apiClient.post<Decision>(`/decisions/${id}/start/`)).data,
  complete: async (id: string) => (await apiClient.post<Decision>(`/decisions/${id}/complete/`)).data,
  cancel:   async (id: string, reason?: string) =>
    (await apiClient.post<Decision>(`/decisions/${id}/cancel/`, { reason })).data,

  convertToActionPlan: async (
    id: string,
    payload?: { title?: string; description_md?: string; target_end_date?: string; tasks?: any[] },
  ) =>
    (await apiClient.post<ActionPlan>(`/decisions/${id}/convert-to-action-plan/`, payload ?? {})).data,

  history: async (id: string) =>
    (await apiClient.get<any[]>(`/decisions/${id}/history/`)).data,
  listComments: async (id: string) =>
    (await apiClient.get<any[]>(`/decisions/${id}/comments/`)).data,
  addComment: async (id: string, body_md: string) =>
    (await apiClient.post(`/decisions/${id}/comments/`, { body_md })).data,
  postpone: async (id: string, deadline?: string) =>
    (await apiClient.post<Decision>(`/decisions/${id}/postpone/`, { deadline })).data,
  stats: async () =>
    (await apiClient.get<DecisionStats>('/decisions/stats/')).data,
}

export type DecisionStats = {
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  by_impact: Record<string, number>
  overdue: number
  approved: number
  completed: number
  pending: number
  confidential: number
}

export const decisionsKeys = {
  all: ['decisions'] as const,
  list: (f: DecisionFilters) => [...decisionsKeys.all, 'list', f] as const,
  detail: (id: string) => [...decisionsKeys.all, 'detail', id] as const,
  history: (id: string) => [...decisionsKeys.detail(id), 'history'] as const,
  comments: (id: string) => [...decisionsKeys.detail(id), 'comments'] as const,
  mine: () => [...decisionsKeys.all, 'mine'] as const,
}
