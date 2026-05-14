import { apiClient } from '@/api/client'
import type { BetaDashboard } from '@/types'

export const dashboardApi = {
  beta: async () => (await apiClient.get<BetaDashboard>('/dashboard/beta/')).data,
}
