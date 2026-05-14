import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'

export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: false,
})

apiClient.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken
  if (token) cfg.headers!.Authorization = `Bearer ${token}`
  return cfg
})

apiClient.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    if (err.response?.status === 401) {
      const refresh = useAuthStore.getState().refreshToken
      if (refresh) {
        try {
          const r = await axios.post(`${API_BASE}/auth/refresh/`, { refresh })
          useAuthStore.getState().setTokens((r.data as any).access, refresh)
          // rejouer la requête
          const original = err.config as InternalAxiosRequestConfig
          original.headers!.Authorization = `Bearer ${(r.data as any).access}`
          return apiClient.request(original)
        } catch {
          useAuthStore.getState().logout()
        }
      } else {
        useAuthStore.getState().logout()
      }
    }
    return Promise.reject(err)
  },
)
