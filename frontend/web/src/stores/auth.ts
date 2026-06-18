import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type { UserMini } from '@/types'

export interface OrgMembership {
  organization_id: string
  organization_name: string
  organization_slug: string
  logo: string
  primary_color: string
  secondary_color: string
  is_owner: boolean
  is_executive: boolean
  role_label: string
  subsidiary_id: string | null
  subsidiary_name: string | null
  is_current: boolean
}

type AuthState = {
  accessToken: string | null
  refreshToken: string | null
  user: UserMini | null
  // ─── Multi-organisations ──
  memberships: OrgMembership[]
  currentOrganizationId: string | null

  setTokens: (access: string, refresh: string | null) => void
  setUser: (u: UserMini) => void
  setMemberships: (m: OrgMembership[]) => void
  setCurrentOrganizationId: (id: string | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      memberships: [],
      currentOrganizationId: null,

      setTokens: (access, refresh) => set({ accessToken: access, refreshToken: refresh }),
      setUser: (user) => set({ user }),
      setMemberships: (memberships) => set({ memberships }),
      setCurrentOrganizationId: (currentOrganizationId) => set({ currentOrganizationId }),
      logout: () => set({
        accessToken: null, refreshToken: null, user: null,
        memberships: [], currentOrganizationId: null,
      }),
    }),
    { name: 'codir-auth' },
  ),
)

/** Helper : retourne le membership courant depuis le store. */
export function useCurrentMembership(): OrgMembership | null {
  return useAuthStore((s) => {
    if (!s.currentOrganizationId) {
      return s.memberships.find((m) => m.is_current) ?? s.memberships[0] ?? null
    }
    return s.memberships.find((m) => m.organization_id === s.currentOrganizationId) ?? null
  })
}
