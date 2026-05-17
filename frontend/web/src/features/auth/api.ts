import { apiClient } from '@/api/client'
import type { UserMini } from '@/types'

export type LoginResponse = { access: string; refresh: string }

/**
 * Si le user a MFA activé, le login étape 1 retourne ce shape au lieu des tokens.
 * Le frontend doit alors demander le code TOTP et appeler `verifyMfa`.
 */
export type MfaChallengeResponse = {
  mfa_required: true
  challenge_token: string
  method: 'totp'
  email: string
}

export type MfaSetupResponse = {
  secret: string
  qr_url: string  // data:image/png;base64,...
  issuer: string
  account: string
}

export const authApi = {
  login: async (email: string, password: string) => {
    // Peut retourner LoginResponse OU MfaChallengeResponse
    const r = await apiClient.post<LoginResponse | MfaChallengeResponse>(
      '/auth/login/', { email, password },
    )
    return r.data as any
  },
  verifyMfa: async (challenge_token: string, code: string) => {
    const r = await apiClient.post<LoginResponse>(
      '/auth/mfa/verify/', { challenge_token, code },
    )
    return r.data
  },
  me: async () => {
    const r = await apiClient.get<UserMini>('/auth/me/')
    return r.data
  },
  // ─── MFA setup (user déjà loggué) ───
  setupMfa: async () => {
    const r = await apiClient.post<MfaSetupResponse>('/auth/mfa/setup/')
    return r.data
  },
  verifyMfaSetup: async (code: string) => {
    const r = await apiClient.post<{ detail: string; mfa_enabled: boolean }>(
      '/auth/mfa/verify-setup/', { code },
    )
    return r.data
  },
  disableMfa: async (password: string) => {
    const r = await apiClient.post<{ detail: string; mfa_enabled: boolean }>(
      '/auth/mfa/disable/', { password },
    )
    return r.data
  },
}
