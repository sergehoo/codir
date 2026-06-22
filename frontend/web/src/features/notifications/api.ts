import { apiClient } from '@/api/client'
import type { Notification, Paginated } from '@/types'

// ─── Types préférences ───────────────────────────────
export type NotificationPreference = {
  id: string
  email_enabled: boolean
  internal_enabled: boolean
  sms_enabled: boolean
  whatsapp_enabled: boolean
  push_enabled: boolean
  task_assignment_email: boolean
  task_delegation_email: boolean
  daily_task_reminder: boolean
  manager_summary: boolean
  due_soon_alert: boolean
  overdue_alert: boolean
  decision_alerts: boolean
  meeting_alerts: boolean
  // Agent IA proactif (Lot 2) — default true côté backend
  proactive_agent_enabled: boolean
  quiet_hours_start: string | null
  quiet_hours_end: string | null
  locale: string
  updated_at: string
}

export type NotificationsSummary = {
  unread: number
  total: number
  latest: Notification[]
}

export type DashboardNotifSummary = {
  unread_notifications: number
  open_tasks: number
  overdue_tasks: number
  due_soon_tasks: number
  critical_tasks: number
  manager_scope?: { subsidiary?: string | null; direction?: string | null }
  manager_summary?: {
    open: number
    overdue: number
    blocked: number
    critical: number
    progress_avg: number
    decisions_pending: number
    top_tasks: Array<{
      id: string
      title: string
      due_date: string | null
      status: string
      priority: string
      assignee__first_name?: string
      assignee__last_name?: string
    }>
  }
}

export const notificationsKeys = {
  all: ['notifications'] as const,
  list: (params?: Record<string, unknown>) => ['notifications', 'list', params ?? {}] as const,
  unread: () => ['notifications', 'unread'] as const,
  summary: () => ['notifications', 'summary'] as const,
  preference: () => ['notifications', 'preference'] as const,
  dashboard: () => ['notifications', 'dashboard'] as const,
}

export const notificationsApi = {
  list: async (params?: { unread?: boolean; event?: string; channel?: string }) =>
    (await apiClient.get<Paginated<Notification> | Notification[]>('/notifications/', {
      params: {
        ...(params?.unread ? { unread: 'true' } : {}),
        ...(params?.event ? { event: params.event } : {}),
        ...(params?.channel ? { channel: params.channel } : {}),
      },
    })).data,

  markRead: async (id: string) =>
    (await apiClient.post<Notification>(`/notifications/${id}/mark-read/`)).data,

  markAllRead: async () =>
    (await apiClient.post('/notifications/mark-all-read/')).data,

  unreadCount: async () =>
    (await apiClient.get<{ unread: number }>('/notifications/unread-count/')).data,

  summary: async () =>
    (await apiClient.get<NotificationsSummary>('/notifications/summary/')).data,

  preference: async () =>
    (await apiClient.get<NotificationPreference>('/notifications/preferences/me/')).data,

  updatePreference: async (patch: Partial<NotificationPreference>) =>
    (await apiClient.patch<NotificationPreference>('/notifications/preferences/me/', patch)).data,

  testEmail: async () =>
    (await apiClient.post<{ detail: string }>('/notifications/test-email/')).data,

  dashboardSummary: async () =>
    (await apiClient.get<DashboardNotifSummary>('/notifications/dashboard/summary/')).data,
}

// Extension action-plans : assign + remind (delegate/postpone/cancel sont dans actionPlansApi)
export const taskActionsApi = {
  assign: async (taskId: string, assignee: string) =>
    (await apiClient.post(`/action-plans/tasks/${taskId}/assign/`, { assignee })).data,
  remind: async (taskId: string) =>
    (await apiClient.post(`/action-plans/tasks/${taskId}/remind/`)).data,
}
