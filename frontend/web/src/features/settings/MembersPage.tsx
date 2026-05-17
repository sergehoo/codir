/**
 * MembersPage — vue admin des membres CODIR avec filtrage par filiale.
 */
import { useQuery } from '@tanstack/react-query'
import { Building2, Crown, Mail, Phone, Search, Users } from 'lucide-react'
import { useMemo, useState } from 'react'

import { apiClient } from '@/api/client'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import { StatsBar } from '@/components/widgets/StatsBar'
import type { Paginated } from '@/types'

interface Member {
  id: string
  user: string
  user_detail: {
    id: string
    email: string
    first_name: string
    last_name: string
    phone_e164?: string
    is_executive?: boolean
  }
  is_owner: boolean
  is_executive: boolean
  is_active: boolean
  subsidiary: string | null
  subsidiary_name: string | null
  role_codes: string[]
}

export function MembersPage() {
  const [search, setSearch] = useState('')
  const [subFilter, setSubFilter] = useState<string>('')

  const { data: members, isLoading, error } = useQuery({
    queryKey: ['settings', 'members'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<Member> | Member[]>(
        '/auth/memberships/?page_size=200',
      )
      return Array.isArray(r.data) ? r.data : r.data.results ?? []
    },
  })

  const list = members ?? []

  // Filtres
  const filtered = useMemo(() => {
    return list.filter((m) => {
      if (subFilter && m.subsidiary !== subFilter) return false
      if (search) {
        const s = search.toLowerCase()
        const u = m.user_detail
        const full = `${u?.first_name ?? ''} ${u?.last_name ?? ''} ${u?.email ?? ''}`.toLowerCase()
        if (!full.includes(s)) return false
      }
      return true
    })
  }, [list, search, subFilter])

  // Liste unique des filiales pour le filtre
  const subsidiaries = useMemo(() => {
    const map = new Map<string, string>()
    list.forEach((m) => {
      if (m.subsidiary && m.subsidiary_name) {
        map.set(m.subsidiary, m.subsidiary_name)
      }
    })
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]))
  }, [list])

  // Stats globales
  const stats = useMemo(() => ({
    total: list.length,
    actifs: list.filter((m) => m.is_active).length,
    execs: list.filter((m) => m.is_executive).length,
    transverses: list.filter((m) => !m.subsidiary).length,
  }), [list])

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Paramètres"
        title="Membres CODIR"
        description={`Liste de l'ensemble des collaborateurs rattachés à l'organisation.`}
      />

      <section className="px-10 pt-6 -mt-2">
        <StatsBar items={[
          { label: 'Total',          value: stats.total,      tone: 'copper' },
          { label: 'Actifs',         value: stats.actifs,     tone: 'success' },
          { label: 'Membres COMEX',  value: stats.execs,      tone: 'info' },
          { label: 'Groupe transverse', value: stats.transverses, tone: 'warning' },
        ]} />
      </section>

      <section className="px-10 py-6">
        {/* Filtres */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher par nom ou email…"
              className="w-full pl-9 pr-3 py-2 rounded-md bg-bg-elevated border border-border text-sm"
            />
          </div>
          <select
            value={subFilter}
            onChange={(e) => setSubFilter(e.target.value)}
            className="bg-bg-elevated border border-border rounded-md px-3 py-2 text-sm min-w-[200px]"
          >
            <option value="">Toutes filiales</option>
            {subsidiaries.map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
            <option value="__none__">— Groupe transverse —</option>
          </select>
        </div>

        {isLoading && <SkeletonList rows={5} />}

        {!isLoading && error && (
          <div className="card p-12 text-center">
            <Users size={28} className="mx-auto text-danger mb-3" strokeWidth={1.5} />
            <p className="text-danger text-sm font-medium">Impossible de charger les membres.</p>
            <p className="text-fg-muted text-xs mt-2">
              {(error as any)?.response?.status === 403
                ? 'Vous n\'avez pas la permission d\'accéder à la liste des membres.'
                : (error as any)?.response?.status === 401
                  ? 'Session expirée — reconnectez-vous.'
                  : (error as any)?.message || 'Erreur réseau ou serveur.'}
            </p>
          </div>
        )}

        {!isLoading && !error && filtered.length === 0 && list.length === 0 && (
          <div className="card p-12 text-center">
            <Users size={28} className="mx-auto text-fg-subtle mb-3" strokeWidth={1.5} />
            <p className="text-fg-muted text-sm">Aucun membre dans cette organisation.</p>
            <p className="text-fg-subtle text-xs mt-2">
              Lancez la commande <code className="font-mono bg-bg-base px-1.5 rounded">seed_kaydan</code> pour créer les 16 membres initiaux.
            </p>
          </div>
        )}

        {!isLoading && !error && filtered.length === 0 && list.length > 0 && (
          <div className="text-fg-muted text-center py-12">
            Aucun membre ne correspond aux filtres.
            <div className="mt-3">
              <button
                onClick={() => { setSearch(''); setSubFilter('') }}
                className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold"
              >
                Réinitialiser
              </button>
            </div>
          </div>
        )}

        {filtered.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-border bg-bg-elevated">
            <table className="w-full text-sm">
              <thead className="bg-bg-base text-2xs uppercase tracking-widest text-fg-muted">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold">Nom</th>
                  <th className="text-left px-4 py-3 font-semibold">Email</th>
                  <th className="text-left px-4 py-3 font-semibold">Filiale</th>
                  <th className="text-left px-4 py-3 font-semibold">Rôle</th>
                  <th className="text-left px-4 py-3 font-semibold">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((m) => (
                  <tr key={m.id} className="hover:bg-bg-base/50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-copper-gradient grid place-items-center text-white text-xs font-medium shrink-0">
                          {(m.user_detail.first_name?.[0] || m.user_detail.email[0]).toUpperCase()}
                          {(m.user_detail.last_name?.[0] || '').toUpperCase()}
                        </div>
                        <div>
                          <div className="font-medium">
                            {m.user_detail.first_name} {m.user_detail.last_name}
                          </div>
                          {m.user_detail.phone_e164 && (
                            <div className="text-2xs text-fg-muted flex items-center gap-1 mt-0.5">
                              <Phone size={10} /> {m.user_detail.phone_e164}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-fg-muted">
                      <div className="flex items-center gap-1.5">
                        <Mail size={12} />
                        {m.user_detail.email}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {m.subsidiary_name ? (
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <Building2 size={12} className="text-fg-muted" />
                          {m.subsidiary_name}
                        </span>
                      ) : (
                        <span className="text-2xs italic text-fg-subtle">Groupe transverse</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {m.is_executive && (
                        <span className="inline-flex items-center gap-1 text-2xs uppercase tracking-wider font-semibold text-copper-500">
                          <Crown size={11} /> COMEX
                        </span>
                      )}
                      {!m.is_executive && (m.role_codes?.length ?? 0) > 0 && (
                        <span className="text-2xs text-fg-muted">
                          {m.role_codes.join(', ')}
                        </span>
                      )}
                      {!m.is_executive && (m.role_codes?.length ?? 0) === 0 && (
                        <span className="text-2xs italic text-fg-subtle">Membre</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {m.is_active ? (
                        <span className="px-2 py-0.5 rounded text-2xs font-semibold bg-green-100 text-green-800">
                          Actif
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-2xs font-semibold bg-slate-100 text-slate-700">
                          Inactif
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
