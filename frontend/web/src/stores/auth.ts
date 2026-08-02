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
  surface_color: string
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

/**
 * Normalise en tableau tout ce qui peut arriver dans `memberships`.
 *
 * Trois sources de corruption possibles :
 *   1. Un état persisté dans localStorage écrit par une version antérieure
 *      du schéma (clé absente, ou valeur d'un autre type).
 *   2. Une réponse API paginée `{count, results: [...]}` au lieu d'une liste
 *      nue, si la pagination DRF venait à être activée globalement.
 *   3. Un échec réseau renvoyant `undefined` / une chaîne d'erreur HTML.
 *
 * Sans cette coercition, `memberships.find(...)` lève
 * « e.memberships.find is not a function » et fait planter tout le Shell,
 * l'utilisateur se retrouvant devant un écran d'erreur sans recours.
 */
/**
 * Référence stable pour le cas dégradé. Indispensable : un `[]` littéral
 * créerait une nouvelle référence à chaque appel du sélecteur zustand
 * (comparaison Object.is) et déclencherait une boucle de re-render.
 */
const EMPTY_MEMBERSHIPS: OrgMembership[] = []

function coerceMemberships(value: unknown): OrgMembership[] {
  if (Array.isArray(value)) return value as OrgMembership[]
  if (value && typeof value === 'object') {
    const results = (value as { results?: unknown }).results
    if (Array.isArray(results)) return results as OrgMembership[]
  }
  return EMPTY_MEMBERSHIPS
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
      setMemberships: (memberships) => set({
        memberships: coerceMemberships(memberships),
      }),
      setCurrentOrganizationId: (currentOrganizationId) => set({ currentOrganizationId }),
      logout: () => set({
        accessToken: null, refreshToken: null, user: null,
        memberships: [], currentOrganizationId: null,
      }),
    }),
    {
      name: 'codir-auth',
      version: 2,
      /**
       * Réhydratation défensive : le state venant du localStorage n'est pas
       * de confiance (schéma d'une ancienne version, écriture partielle,
       * édition manuelle). On force `memberships` à être un tableau avant
       * qu'il n'atteigne le moindre composant.
       */
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<AuthState>
        return {
          ...current,
          ...p,
          memberships: coerceMemberships(p.memberships),
        }
      },
      migrate: (persisted) => {
        const p = (persisted ?? {}) as Partial<AuthState>
        return { ...p, memberships: coerceMemberships(p.memberships) }
      },
    },
  ),
)

/** Helper : retourne le membership courant depuis le store. */
export function useCurrentMembership(): OrgMembership | null {
  return useAuthStore((s) => {
    const list = Array.isArray(s.memberships) ? s.memberships : EMPTY_MEMBERSHIPS
    if (!s.currentOrganizationId) {
      return list.find((m) => m.is_current) ?? list[0] ?? null
    }
    return list.find((m) => m.organization_id === s.currentOrganizationId) ?? null
  })
}

/**
 * Accès sûr à la liste des memberships — à préférer à
 * `useAuthStore((s) => s.memberships)` dans les composants.
 *
 * Retourne toujours un tableau, avec une référence stable dans le cas
 * dégradé (pas de boucle de re-render).
 */
export function useMemberships(): OrgMembership[] {
  return useAuthStore((s) =>
    (Array.isArray(s.memberships) ? s.memberships : EMPTY_MEMBERSHIPS),
  )
}
