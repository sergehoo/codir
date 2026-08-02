// Hook : charge automatiquement la liste des memberships du user dès qu'on
// a un access token (au login OU au boot avec un token persisté).
//
// Branchée dans Shell — exécuté à chaque montage de la zone authentifiée.
// Met à jour le store auth.memberships + currentOrganizationId.
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { useAuthStore } from '@/stores/auth'

import { organizationsApi, organizationsKeys } from './api'

export function useMembershipsBootstrap() {
  const accessToken = useAuthStore((s) => s.accessToken)
  const setMemberships = useAuthStore((s) => s.setMemberships)
  const setCurrentOrganizationId = useAuthStore((s) => s.setCurrentOrganizationId)
  const currentOrganizationId = useAuthStore((s) => s.currentOrganizationId)

  const { data, isSuccess } = useQuery({
    queryKey: organizationsKeys.memberships(),
    queryFn: () => organizationsApi.myMemberships(),
    enabled: !!accessToken,
    staleTime: 5 * 60_000,  // 5 min — change rarement
  })

  useEffect(() => {
    if (!isSuccess || !data) return

    // ⚠ Ne jamais présumer que la réponse est un tableau : une pagination
    // DRF activée globalement renverrait {count, results}, et une erreur
    // réseau interceptée pourrait renvoyer autre chose. Sans ce garde-fou,
    // `data.some(...)` casse tout le Shell au boot.
    const list = Array.isArray(data) ? data : []
    setMemberships(list)

    if (list.length === 0) return

    // Si aucune org courante setée ou si la courante n'existe plus dans la liste,
    // on bascule sur celle marquée is_current (depuis le JWT) ou la 1ère.
    const isStillValid = list.some(
      (m) => m.organization_id === currentOrganizationId,
    )
    if (!currentOrganizationId || !isStillValid) {
      const current = list.find((m) => m.is_current) ?? list[0]
      if (current) {
        setCurrentOrganizationId(current.organization_id)
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuccess, data])
}
