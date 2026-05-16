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

export const dashboardApi = {
  beta: async () => (await apiClient.get<BetaDashboard>('/dashboard/beta/')).data,
  epiScore: async (historyDays = 90) =>
    (await apiClient.get<EpiScoreResponse>(
      `/dashboard/epi-score/?history_days=${historyDays}`,
    )).data,
}
