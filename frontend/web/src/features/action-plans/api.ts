import { apiClient } from '@/api/client'
import type { ActionPlan, ActionTask, Paginated } from '@/types'

export type ActionTaskStats = {
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  overdue: number
  done: number
  due_this_week: number
  unassigned: number
}

export type ActionPlanStats = {
  total: number
  by_status: Record<string, number>
  avg_progress: number
  completed: number
  blocked: number
}

export const actionPlansApi = {
  list: async () =>
    (await apiClient.get<Paginated<ActionPlan> | ActionPlan[]>('/action-plans/')).data,
  retrieve: async (id: string) =>
    (await apiClient.get<ActionPlan>(`/action-plans/${id}/`)).data,
  stats: async () =>
    (await apiClient.get<ActionPlanStats>('/action-plans/stats/')).data,

  // ─── Plan tasks ───────────────────────────────────────
  listTasks: async (id: string) =>
    (await apiClient.get<ActionTask[]>(`/action-plans/${id}/tasks/`)).data,
  addTask: async (id: string, payload: Partial<ActionTask>) =>
    (await apiClient.post<ActionTask>(`/action-plans/${id}/tasks/`, payload)).data,

  // ─── Task actions ─────────────────────────────────────
  taskDetail: async (id: string) =>
    (await apiClient.get<ActionTask>(`/action-plans/tasks/${id}/`)).data,
  taskStats: async () =>
    (await apiClient.get<ActionTaskStats>('/action-plans/tasks/stats/')).data,
  updateProgress: async (id: string, payload: { progress_percent: number; status?: string }) =>
    (await apiClient.post<ActionTask>(`/action-plans/tasks/${id}/update-progress/`, payload)).data,
  completeTask: async (id: string) =>
    (await apiClient.post<ActionTask>(`/action-plans/tasks/${id}/complete/`)).data,
  cancelTask: async (id: string, reason?: string) =>
    (await apiClient.post<ActionTask>(`/action-plans/tasks/${id}/cancel/`, { reason })).data,
  delegateTask: async (id: string, assignee: string, note?: string) =>
    (await apiClient.post<ActionTask>(`/action-plans/tasks/${id}/delegate/`, { assignee, note })).data,
  postponeTask: async (id: string, due_date: string, reason?: string) =>
    (await apiClient.post<ActionTask>(`/action-plans/tasks/${id}/postpone/`, { due_date, reason })).data,

  myTasks: async () =>
    (await apiClient.get<Paginated<ActionTask> | ActionTask[]>('/action-plans/tasks/my-tasks/')).data,
}

export const plansKeys = {
  all: ['action-plans'] as const,
  list: () => [...plansKeys.all, 'list'] as const,
  detail: (id: string) => [...plansKeys.all, 'detail', id] as const,
  tasks: (id: string) => [...plansKeys.all, 'tasks', id] as const,
  stats: () => [...plansKeys.all, 'stats'] as const,
  taskStats: () => [...plansKeys.all, 'task-stats'] as const,
  myTasks: () => ['my-tasks'] as const,
}
