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

/**
 * Force la fin de session : purge le store, puis redirige vers /login en
 * hard reload pour éviter tout état UI fantôme (placeholder "Bonjour, …",
 * widgets affichant des données stale, etc.).
 */
function forceLogout(reason: 'expired' | 'invalid' = 'expired') {
  try {
    useAuthStore.getState().logout()
  } catch {
    /* ignore */
  }
  // Évite le double-redirect si on est déjà sur /login
  if (!window.location.pathname.startsWith('/login')) {
    window.location.replace(`/login?reason=${reason}`)
  }
}

apiClient.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const original = err.config as InternalAxiosRequestConfig & { _retried?: boolean }
    const url = original?.url ?? ''
    const isRefreshCall = url.includes('/auth/refresh')

    // ── 401 sur le refresh lui-même : session définitivement expirée ──
    if (err.response?.status === 401 && isRefreshCall) {
      forceLogout('expired')
      return Promise.reject(err)
    }

    // ── 401 sur un appel métier : tenter un refresh une seule fois ──
    if (err.response?.status === 401 && !original?._retried) {
      const refresh = useAuthStore.getState().refreshToken
      if (!refresh) {
        forceLogout('expired')
        return Promise.reject(err)
      }
      try {
        const r = await axios.post(
          `${API_BASE}/auth/refresh/`,
          { refresh },
          { headers: { 'Content-Type': 'application/json' } },
        )
        const newAccess = (r.data as any).access
        useAuthStore.getState().setTokens(newAccess, refresh)
        original.headers!.Authorization = `Bearer ${newAccess}`
        original._retried = true
        return apiClient.request(original)
      } catch {
        forceLogout('expired')
        return Promise.reject(err)
      }
    }

    return Promise.reject(err)
  },
)
