import { apiClient } from '@/api/client'
import type { BetaDashboard } from '@/types'

export interface EpiScoreCurrent {
  overall_score: number
  completion_score: number
  punctuality_score: number
  velocity_score: number
  quorum_score: number
  overdue_penalty: number
  tasks_total: number
  tasks_done: number
  tasks_done_on_time: number
  tasks_overdue: number
  avg_days_to_close: number
  meetings_total: number
  meetings_quorum_reached: number
  weights: { completion: number; punctuality: number; velocity: number; quorum: number }
  windows: { tasks_days: number; velocity_days: number; meetings_days: number }
  computed_at: string
}

export interface EpiScoreHistoryPoint {
  date: string
  score: number
  delta: number
}

export interface EpiScoreTrend {
  min: number
  max: number
  delta: number
  direction: 'up' | 'down' | 'flat'
  first_score: number
  last_score: number
}

export interface EpiScoreResponse {
  current: EpiScoreCurrent
  history: EpiScoreHistoryPoint[]
  trend: EpiScoreTrend
}

export type HealthLabel = 'healthy' | 'watch' | 'at_risk' | 'critical'

export interface WatchlistItem {
  kind: 'plan' | 'decision'
  id: string
  title: string
  url: string
  score: number
  label: HealthLabel
  reasons: string[]
  owner_name: string
  priority: 'low' | 'medium' | 'high' | 'critical' | null
  progress_percent: number | null
}

export interface WatchlistResponse {
  items: WatchlistItem[]
  count: number
  generated_at: string
}

export const dashboardApi = {
  beta: async () => (await apiClient.get<BetaDashboard>('/dashboard/beta/')).data,
  epiScore: async (historyDays = 90) =>
    (await apiClient.get<EpiScoreResponse>(
      `/dashboard/epi-score/?history_days=${historyDays}`,
    )).data,
  watchlist: async (limit = 10) =>
    (await apiClient.get<WatchlistResponse>(
      `/dashboard/watchlist/?limit=${limit}`,
    )).data,
  briefing: async () =>
    (await apiClient.get<DailyBriefing>('/dashboard/briefing/today/')).data,
}

export interface DailyBriefing {
  markdown: string
  vocal_text: string
  summary: string
  generated_at: string
  stats: {
    my_tasks_today: number
    meetings_today: number
    decisions_pending: number
    at_risk: number
  }
}
