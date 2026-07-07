/**
 * useSubsidiariesDirections — hook réutilisable pour peupler les selects
 * "Filiale" et "Direction" (dépendante) dans les formulaires de création.
 *
 * Utilisé par :
 *   - Modal "Nouvelle décision" (DecisionsListPage)
 *   - Modal "Nouveau dossier" (ActionPlansListPage)
 *   - Modal "Nouvelle décision" (LiveCodirMode)
 *
 * Comportement :
 *   - Liste toutes les filiales de l'org courante (une fois, cache 5 min).
 *   - Liste toutes les directions filtrées par filiale si `subsidiaryId` fourni,
 *     sinon toutes les directions de l'org.
 */
import { useQuery } from '@tanstack/react-query'

import { apiClient } from '@/api/client'
import type { Paginated } from '@/types'


export interface Subsidiary {
  id: string
  name: string
  country?: string
  currency?: string
  parent?: string | null
  is_active?: boolean
}


export interface Direction {
  id: string
  name: string
  code?: string
  color?: string
  subsidiary: string | null
  subsidiary_name?: string | null
}


export function useSubsidiaries() {
  return useQuery({
    queryKey: ['org', 'subsidiaries'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<Subsidiary> | Subsidiary[]>(
        '/organizations/subsidiaries/?page_size=200',
      )
      return Array.isArray(r.data) ? r.data : (r.data.results ?? [])
    },
    staleTime: 5 * 60_000,
  })
}


export function useDirections(subsidiaryId?: string) {
  return useQuery({
    queryKey: ['org', 'directions', subsidiaryId || '__all__'],
    queryFn: async () => {
      const params = subsidiaryId ? `?subsidiary=${subsidiaryId}` : ''
      const r = await apiClient.get<Paginated<Direction> | Direction[]>(
        `/governance/directions/${params}`,
      )
      return Array.isArray(r.data) ? r.data : (r.data.results ?? [])
    },
    staleTime: 5 * 60_000,
  })
}
