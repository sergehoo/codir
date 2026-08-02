// Hook : orchestre le changement d'organisation côté frontend.
//
// Workflow :
//   1. Appel POST /auth/switch-organization/ avec org_id cible
//   2. Backend renvoie nouveaux access+refresh tokens (org_id mis à jour)
//   3. On les pose dans le store auth
//   4. On met à jour memberships + currentOrganizationId
//   5. On invalide TOUTES les queries TanStack pour recharger les données
//      filtrées par la nouvelle org
//   6. Toast de confirmation
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { useAIChatStore } from '@/features/ai-chat/store'
import { useAuthStore, useMemberships, type OrgMembership } from '@/stores/auth'

import { organizationsApi, organizationsKeys } from './api'

export function useOrganizationSwitch() {
  const qc = useQueryClient()
  const setTokens = useAuthStore((s) => s.setTokens)
  const setMemberships = useAuthStore((s) => s.setMemberships)
  const setCurrentOrganizationId = useAuthStore((s) => s.setCurrentOrganizationId)
  const memberships = useMemberships()

  return useMutation({
    mutationFn: async (target: OrgMembership | string) => {
      const orgId = typeof target === 'string' ? target : target.organization_id
      const r = await organizationsApi.switchOrganization(orgId)

      // 1. Pose les nouveaux tokens
      setTokens(r.access, r.refresh)

      // 2. Met à jour le membership courant + flag is_current
      setCurrentOrganizationId(r.organization.id)
      const refreshed: OrgMembership[] = memberships.map((m) => ({
        ...m,
        is_current: m.organization_id === r.organization.id,
      }))
      setMemberships(refreshed)

      // 3. Multi-org : reset l'état du chat IA car les conversations,
      // le contexte page (meeting_id, decision_id…) et le prompt initial
      // appartiennent à l'ancienne org. Sans ce reset, le sidebar afficherait
      // une conversation introuvable (404) ou injecterait un contexte d'objet
      // qui n'appartient plus à la nouvelle org.
      useAIChatStore.getState().resetForOrgSwitch()

      return r
    },
    onSuccess: async (r) => {
      // 3. Invalide TOUT le cache de données métier pour forcer un refresh
      // (réunions, décisions, plans, tâches, dashboard, notifications…)
      // On garde seulement les queries auth/orgs car elles sont déjà à jour.
      await qc.invalidateQueries({
        predicate: (q) => {
          const key = String(q.queryKey[0] ?? '')
          // ne PAS invalider les memberships eux-mêmes (déjà set)
          return !['organizations', 'auth'].some((prefix) => key.startsWith(prefix))
        },
      })
      // 4. Rafraîchit explicitement la liste des memberships (is_current update)
      qc.invalidateQueries({ queryKey: organizationsKeys.memberships() })

      toast.success(`Vous êtes maintenant sur ${r.organization.name}`, {
        description: `Rôle : ${r.organization.role_label}`,
        duration: 3000,
      })
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail || e?.message || 'Changement refusé'
      toast.error('Impossible de changer d\'organisation', { description: detail })
    },
  })
}
