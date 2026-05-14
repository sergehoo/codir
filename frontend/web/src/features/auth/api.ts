import { apiClient } from '@/api/client'
import type { UserMini } from '@/types'

export type LoginResponse = { access: string; refresh: string }

export const authApi = {
  login: async (email: string, password: string) => {
    const r = await apiClient.post<LoginResponse>('/auth/login/', { email, password })
    return r.data
  },
  me: async () => {
    const r = await apiClient.get<UserMini>('/auth/me/')
    return r.data
  },
}
