import { apiClient } from '@/api/client'
import type { UserMini } from '@/types'

export const accountsApi = {
  /** Annuaire des utilisateurs du tenant courant — utilisé pour les selects. */
  listUsers: async () =>
    (await apiClient.get<UserMini[] | { results: UserMini[] }>('/auth/users/')).data,
}

export const usersKeys = {
  all: ['users'] as const,
}

export function unwrapList<T>(data: T[] | { results: T[] }): T[] {
  return Array.isArray(data) ? data : (data?.results ?? [])
}
