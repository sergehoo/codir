// API client multi-organisations.
import { apiClient } from '@/api/client'
import type { OrgMembership } from '@/stores/auth'

export interface SwitchOrgResponse {
  access: string
  refresh: string
  organization: {
    id: string
    name: string
    slug: string
    logo: string
    primary_color: string
    secondary_color: string
    surface_color: string
    role_label: string
  }
}

export interface CurrentOrg {
  id: string
  name: string
  slug: string
  country?: string
  timezone?: string
  currency?: string
  plan?: string
  is_active?: boolean
  primary_color: string
  secondary_color: string
  surface_color: string
  logo: string
}

export type UpdateOrgPayload = Partial<
  Pick<CurrentOrg, 'name' | 'logo' | 'primary_color' | 'secondary_color' | 'surface_color'>
>

export const organizationsApi = {
  /**
   * Liste toutes les organisations où le user est membre actif.
   *
   * Normalise à la source : l'endpoint renvoie une liste nue aujourd'hui,
   * mais si la pagination DRF venait à être activée globalement il
   * renverrait `{count, results}`. On garantit ici un tableau, sans quoi
   * tous les `.find` / `.some` en aval cassent le Shell entier.
   */
  myMemberships: async (): Promise<OrgMembership[]> => {
    const { data } = await apiClient.get<
      OrgMembership[] | { results?: OrgMembership[] }
    >('/auth/my-memberships/')
    if (Array.isArray(data)) return data
    if (data && Array.isArray(data.results)) return data.results
    return []
  },

  /** Change l'organisation active — retourne de nouveaux tokens. */
  switchOrganization: async (organization_id: string) =>
    (await apiClient.post<SwitchOrgResponse>(
      '/auth/switch-organization/',
      { organization_id },
    )).data,

  /** Récupère l'organisation courante (full payload). */
  getCurrent: async () =>
    (await apiClient.get<CurrentOrg>('/organizations/me/')).data,

  /** Modifie le branding de l'org courante (admin only). */
  updateCurrent: async (payload: UpdateOrgPayload) =>
    (await apiClient.patch<CurrentOrg>('/organizations/me/', payload)).data,
}

export const organizationsKeys = {
  all: ['organizations'] as const,
  memberships: () => [...organizationsKeys.all, 'memberships'] as const,
  current: () => [...organizationsKeys.all, 'current'] as const,
}
