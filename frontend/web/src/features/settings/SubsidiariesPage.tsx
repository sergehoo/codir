/**
 * SubsidiariesPage — vue des filiales de l'organisation + nombre de membres.
 */
import { useQuery } from '@tanstack/react-query'
import { Building2, MapPin, Users } from 'lucide-react'

import { apiClient } from '@/api/client'
import { EmptyState } from '@/components/widgets/EmptyState'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import type { Paginated } from '@/types'

interface Subsidiary {
  id: string
  name: string
  legal_form?: string
  country: string
  currency: string
  is_active: boolean
  parent?: string | null
  members_count?: number
}

export function SubsidiariesPage() {
  const { data: subs, isLoading, error } = useQuery({
    queryKey: ['settings', 'subsidiaries'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<Subsidiary> | Subsidiary[]>(
        '/organizations/subsidiaries/?page_size=100',
      )
      return Array.isArray(r.data) ? r.data : r.data.results ?? []
    },
  })

  const list = subs ?? []

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Paramètres"
        title="Filiales"
        description={`${list.length} entité(s) juridique(s) rattachées à l'organisation.`}
      />

      <section className="px-10 py-6">
        {isLoading && <SkeletonList rows={4} />}

        {!isLoading && error && (
          <div className="card p-12 text-center">
            <Building2 size={28} className="mx-auto text-danger mb-3" strokeWidth={1.5} />
            <p className="text-danger text-sm font-medium">Impossible de charger les filiales.</p>
            <p className="text-fg-muted text-xs mt-2">
              {(error as any)?.response?.status === 403
                ? 'Vous n\'avez pas la permission d\'accéder aux filiales.'
                : (error as any)?.response?.status === 401
                  ? 'Session expirée — reconnectez-vous.'
                  : (error as any)?.message || 'Erreur réseau ou serveur.'}
            </p>
          </div>
        )}

        {!isLoading && !error && list.length === 0 && (
          <EmptyState
            icon={Building2}
            title="Aucune filiale"
            description="Aucune filiale n'a été créée. Lancez seed_kaydan pour créer les 5 filiales initiales."
          />
        )}

        {list.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {list.map((s) => (
              <div
                key={s.id}
                className="card p-5 hover:border-copper-500/40 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-copper-500/10 grid place-items-center shrink-0">
                    <Building2 size={18} className="text-copper-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="serif text-base font-semibold leading-tight">
                      {s.name}
                    </h3>
                    {s.legal_form && (
                      <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-0.5">
                        {s.legal_form}
                      </div>
                    )}
                  </div>
                  {s.is_active ? (
                    <span className="px-2 py-0.5 rounded text-2xs font-semibold bg-green-100 text-green-800">
                      Actif
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-2xs font-semibold bg-slate-100 text-slate-700">
                      Inactif
                    </span>
                  )}
                </div>

                <div className="divider my-4" />

                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-fg-muted">
                    <MapPin size={13} />
                    <span>{s.country} · {s.currency}</span>
                  </div>
                  {typeof s.members_count === 'number' && (
                    <div className="flex items-center gap-2 text-fg-muted">
                      <Users size={13} />
                      <span>{s.members_count} collaborateur(s)</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
