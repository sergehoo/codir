// API client — Logs admin (activité applicative + connexions).
//
// Endpoints : IsOrganizationAdmin → DG/Owner/Staff uniquement.
import { apiClient } from '@/api/client'

export interface AuditLogDTO {
  id: string
  actor: string | null
  actor_detail: {
    id: string
    email: string
    full_name: string
    first_name?: string
    last_name?: string
  } | null
  action: string
  target_model: string | null
  target_id: string
  target_repr: string
  description: string
  diff_json: Record<string, unknown>
  ip: string | null
  user_agent: string
  created_at: string
}

export interface AccessLogDTO {
  kind: 'success' | 'failed'
  username: string
  user_id: number | null
  user_full_name: string
  ip_address: string | null
  user_agent: string
  path_info: string
  attempt_time: string
  logout_time: string | null
  failures_since_start: number | null
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface AuditLogFilters {
  action?: string
  actor?: string         // user UUID
  search?: string        // texte libre
  date_from?: string     // YYYY-MM-DD
  date_to?: string       // YYYY-MM-DD
  page?: number
  limit?: number
}

export interface AccessLogFilters {
  kind?: 'success' | 'failed' | ''
  username?: string
  date_from?: string
  date_to?: string
  page?: number
  limit?: number
}

function clean(o: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(o)) {
    if (v !== undefined && v !== null && v !== '') out[k] = v
  }
  return out
}

export const logsApi = {
  listAuditLogs: async (filters: AuditLogFilters = {}) =>
    (await apiClient.get<Paginated<AuditLogDTO>>('/audit-logs/', {
      params: clean(filters as Record<string, unknown>),
    })).data,

  listAccessLogs: async (filters: AccessLogFilters = {}) =>
    (await apiClient.get<Paginated<AccessLogDTO>>('/audit-logs/access/', {
      params: clean(filters as Record<string, unknown>),
    })).data,
}
