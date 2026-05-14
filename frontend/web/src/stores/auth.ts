import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type { UserMini } from '@/types'

type AuthState = {
  accessToken: string | null
  refreshToken: string | null
  user: UserMini | null
  setTokens: (access: string, refresh: string | null) => void
  setUser: (u: UserMini) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setTokens: (access, refresh) => set({ accessToken: access, refreshToken: refresh }),
      setUser: (user) => set({ user }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    { name: 'codir-auth' },
  ),
)
