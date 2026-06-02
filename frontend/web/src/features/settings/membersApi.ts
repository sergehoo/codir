// API client — gestion administrative des membres (admin / DG only).
//
// Tous les endpoints attendent une org tenant (envoyée par l'intercepteur axios).
// Permissions backend : IsOrganizationOwner sur les écritures.
import { apiClient } from '@/api/client'

export interface CreateMemberPayload {
  email: string
  first_name?: string
  last_name?: string
  phone_e164?: string
  is_executive?: boolean
  is_owner?: boolean
  subsidiary?: string | null
  direction_ids?: string[]
  role_codes?: string[]
  send_welcome_email?: boolean
}

export interface ReassignPayload {
  subsidiary?: string | null
  direction_ids?: string[]
  role_codes?: string[]
  is_owner?: boolean
  is_executive?: boolean
  send_email?: boolean
}

export interface MembershipDTO {
  id: string
  user: string
  user_detail: {
    id: string
    email: string
    first_name: string
    last_name: string
    full_name: string
    phone_e164?: string
    is_executive?: boolean
  }
  is_owner: boolean
  is_executive: boolean
  is_active: boolean
  expires_at: string | null
  role_codes: string[]
  subsidiary: string | null
  subsidiary_name: string | null
}

export const membersApi = {
  /** Crée un user + membership, envoie email avec credentials. */
  create: async (payload: CreateMemberPayload) =>
    (await apiClient.post<MembershipDTO>('/auth/users/', payload)).data,

  /** Réinitialise le mot de passe (envoi email). */
  resetPassword: async (userId: string) =>
    (await apiClient.post<{ detail: string }>(`/auth/users/${userId}/reset-password/`)).data,

  /** Désactive un compte. */
  deactivate: async (userId: string) =>
    (await apiClient.post<{ detail: string }>(`/auth/users/${userId}/deactivate/`)).data,

  /** Réactive un compte. */
  reactivate: async (userId: string) =>
    (await apiClient.post<{ detail: string }>(`/auth/users/${userId}/reactivate/`)).data,

  /** Met à jour le périmètre d'un membership (filiale + directions + rôles). */
  reassign: async (membershipId: string, payload: ReassignPayload) =>
    (await apiClient.post<MembershipDTO>(
      `/auth/memberships/${membershipId}/reassign/`, payload,
    )).data,
}
