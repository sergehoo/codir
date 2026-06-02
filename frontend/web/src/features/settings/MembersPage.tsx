/**
 * MembersPage — administration des collaborateurs CODIR.
 *
 * Lecture pour tout membre, écriture pour Owner uniquement (backend = 403 sinon).
 * Actions disponibles :
 *  - Créer un membre (avec credentials envoyés par email)
 *  - Réinitialiser le mot de passe (email)
 *  - Modifier l'affectation (filiale / executive / owner)
 *  - Désactiver / Réactiver
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Building2, Crown, KeyRound, Mail, MoreVertical, Phone,
  Search, Settings2, UserPlus, UserX, UserCheck, Users,
} from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'

import { apiClient } from '@/api/client'
import { Modal } from '@/components/widgets/Modal'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import { StatsBar } from '@/components/widgets/StatsBar'
import type { Paginated } from '@/types'
import { cn } from '@/utils/cn'

import { membersApi, type MembershipDTO } from './membersApi'

interface Subsidiary { id: string; name: string }

export function MembersPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [subFilter, setSubFilter] = useState<string>('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editingMember, setEditingMember] = useState<MembershipDTO | null>(null)
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)

  const { data: members, isLoading, error } = useQuery({
    queryKey: ['settings', 'members'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<MembershipDTO> | MembershipDTO[]>(
        '/auth/memberships/?page_size=200',
      )
      return Array.isArray(r.data) ? r.data : r.data.results ?? []
    },
  })

  // Liste des filiales pour les selects (modal create + filtre).
  const { data: subsidiaries } = useQuery<Subsidiary[]>({
    queryKey: ['organizations', 'subsidiaries'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<Subsidiary> | Subsidiary[]>(
        '/organizations/subsidiaries/?page_size=200',
      )
      return Array.isArray(r.data) ? r.data : r.data.results ?? []
    },
    staleTime: 5 * 60_000,
  })

  const invalidateMembers = () =>
    qc.invalidateQueries({ queryKey: ['settings', 'members'] })

  // ─── Mutations ────────────────────────────────────────────
  const resetPwd = useMutation({
    mutationFn: (userId: string) => membersApi.resetPassword(userId),
    onSuccess: (data) => toast.success(data.detail ?? 'Mot de passe réinitialisé. Email envoyé.'),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Réinitialisation refusée.'),
  })
  const deactivate = useMutation({
    mutationFn: (userId: string) => membersApi.deactivate(userId),
    onSuccess: (data) => { toast.success(data.detail ?? 'Compte désactivé.'); invalidateMembers() },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Désactivation refusée.'),
  })
  const reactivate = useMutation({
    mutationFn: (userId: string) => membersApi.reactivate(userId),
    onSuccess: (data) => { toast.success(data.detail ?? 'Compte réactivé.'); invalidateMembers() },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Réactivation refusée.'),
  })

  const list = members ?? []

  const filtered = useMemo(() => {
    return list.filter((m) => {
      if (subFilter === '__none__' && m.subsidiary) return false
      if (subFilter && subFilter !== '__none__' && m.subsidiary !== subFilter) return false
      if (search) {
        const s = search.toLowerCase()
        const u = m.user_detail
        const full = `${u?.first_name ?? ''} ${u?.last_name ?? ''} ${u?.email ?? ''}`.toLowerCase()
        if (!full.includes(s)) return false
      }
      return true
    })
  }, [list, search, subFilter])

  const subOptions = useMemo(() => {
    const map = new Map<string, string>()
    list.forEach((m) => {
      if (m.subsidiary && m.subsidiary_name) map.set(m.subsidiary, m.subsidiary_name)
    })
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]))
  }, [list])

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
        description="Gestion administrative des collaborateurs : création, affectation, réinitialisation de mot de passe."
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
        {/* Filtres + CTA création */}
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
            {subOptions.map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
            <option value="__none__">— Groupe transverse —</option>
          </select>
          <div className="flex-1" />
          <PremiumButton
            onClick={() => setCreateOpen(true)}
            iconLeft={<UserPlus size={14} />}
          >
            Nouveau membre
          </PremiumButton>
        </div>

        {isLoading && <SkeletonList rows={5} />}

        {!isLoading && error && (
          <div className="card p-12 text-center">
            <Users size={28} className="mx-auto text-danger mb-3" strokeWidth={1.5} />
            <p className="text-danger text-sm font-medium">Impossible de charger les membres.</p>
            <p className="text-fg-muted text-xs mt-2">
              {(error as any)?.response?.status === 403
                ? "Vous n'avez pas la permission d'accéder à la liste des membres."
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
            <PremiumButton
              className="mt-4"
              onClick={() => setCreateOpen(true)}
              iconLeft={<UserPlus size={14} />}
            >
              Créer le premier membre
            </PremiumButton>
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
                  <th className="text-right px-4 py-3 font-semibold w-12">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((m) => (
                  <MemberRow
                    key={m.id}
                    member={m}
                    isMenuOpen={openMenuId === m.id}
                    onMenuToggle={(open) => setOpenMenuId(open ? m.id : null)}
                    onEdit={() => setEditingMember(m)}
                    onResetPassword={() => {
                      if (confirm(`Réinitialiser le mot de passe de ${m.user_detail.full_name} ?\nL'email sera envoyé immédiatement.`)) {
                        resetPwd.mutate(m.user_detail.id)
                      }
                      setOpenMenuId(null)
                    }}
                    onDeactivate={() => {
                      if (confirm(`Désactiver le compte de ${m.user_detail.full_name} ?\nIl ne pourra plus se connecter.`)) {
                        deactivate.mutate(m.user_detail.id)
                      }
                      setOpenMenuId(null)
                    }}
                    onReactivate={() => {
                      reactivate.mutate(m.user_detail.id)
                      setOpenMenuId(null)
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <CreateMemberModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        subsidiaries={subsidiaries ?? []}
        onCreated={invalidateMembers}
      />
      <ReassignMemberModal
        member={editingMember}
        onClose={() => setEditingMember(null)}
        subsidiaries={subsidiaries ?? []}
        onSaved={invalidateMembers}
      />
    </div>
  )
}


/* ════════════════════════════════════════════════
   Ligne tableau avec menu d'actions
   ════════════════════════════════════════════════ */

interface MemberRowProps {
  member: MembershipDTO
  isMenuOpen: boolean
  onMenuToggle: (open: boolean) => void
  onEdit: () => void
  onResetPassword: () => void
  onDeactivate: () => void
  onReactivate: () => void
}

function MemberRow({
  member: m, isMenuOpen, onMenuToggle,
  onEdit, onResetPassword, onDeactivate, onReactivate,
}: MemberRowProps) {
  const menuRef = useRef<HTMLDivElement | null>(null)

  return (
    <tr className="hover:bg-bg-base/50">
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
        {m.is_owner && (
          <span className="ml-1 inline-flex text-2xs uppercase tracking-wider font-semibold text-amber-400">
            Owner
          </span>
        )}
        {!m.is_executive && (m.role_codes?.length ?? 0) > 0 && (
          <span className="text-2xs text-fg-muted">{m.role_codes.join(', ')}</span>
        )}
        {!m.is_executive && !m.is_owner && (m.role_codes?.length ?? 0) === 0 && (
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
      <td className="px-4 py-3 relative">
        <div ref={menuRef} className="relative inline-block">
          <button
            type="button"
            onClick={() => onMenuToggle(!isMenuOpen)}
            className="p-1.5 rounded hover:bg-fg/10 text-fg-muted hover:text-fg transition"
            aria-label="Ouvrir le menu d'actions"
          >
            <MoreVertical size={14} />
          </button>
          {isMenuOpen && (
            <div className="absolute right-0 top-full mt-1 min-w-[220px] z-30 bg-bg-elevated border border-border rounded-lg shadow-xl overflow-hidden">
              <MenuAction icon={<Settings2 size={13} />} label="Modifier l'affectation" onClick={() => { onEdit(); onMenuToggle(false) }} />
              <MenuAction icon={<KeyRound size={13} />} label="Réinitialiser le mot de passe" onClick={onResetPassword} />
              {m.is_active ? (
                <MenuAction
                  icon={<UserX size={13} />}
                  label="Désactiver le compte"
                  onClick={onDeactivate}
                  variant="danger"
                />
              ) : (
                <MenuAction
                  icon={<UserCheck size={13} />}
                  label="Réactiver le compte"
                  onClick={onReactivate}
                  variant="success"
                />
              )}
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}

function MenuAction({
  icon, label, onClick, variant = 'default',
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
  variant?: 'default' | 'danger' | 'success'
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2 px-3.5 py-2 text-xs transition text-left',
        variant === 'danger' && 'text-red-400 hover:bg-red-500/10',
        variant === 'success' && 'text-emerald-400 hover:bg-emerald-500/10',
        variant === 'default' && 'text-fg hover:bg-fg/5',
      )}
    >
      {icon} {label}
    </button>
  )
}


/* ════════════════════════════════════════════════
   Modal de création
   ════════════════════════════════════════════════ */

function CreateMemberModal({
  open, onClose, subsidiaries, onCreated,
}: {
  open: boolean
  onClose: () => void
  subsidiaries: Subsidiary[]
  onCreated: () => void
}) {
  const [form, setForm] = useState({
    email: '', first_name: '', last_name: '', phone_e164: '',
    is_executive: false, is_owner: false,
    subsidiary: '' as string | '',
    send_welcome_email: true,
  })

  const reset = () => setForm({
    email: '', first_name: '', last_name: '', phone_e164: '',
    is_executive: false, is_owner: false,
    subsidiary: '', send_welcome_email: true,
  })

  const create = useMutation({
    mutationFn: () => membersApi.create({
      email: form.email.trim().toLowerCase(),
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      phone_e164: form.phone_e164.trim(),
      is_executive: form.is_executive,
      is_owner: form.is_owner,
      subsidiary: form.subsidiary || null,
      send_welcome_email: form.send_welcome_email,
    }),
    onSuccess: () => {
      toast.success("Membre créé. Email avec credentials envoyé.")
      onCreated()
      reset()
      onClose()
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail
        ?? e?.response?.data?.email?.[0]
        ?? "Création refusée."),
  })

  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())

  return (
    <Modal open={open} onClose={() => { reset(); onClose() }} title="Créer un nouveau membre">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Prénom</label>
            <input
              className="input"
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Nom</label>
            <input
              className="input"
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            />
          </div>
        </div>

        <div>
          <label className="label">Email <span className="text-red-400">*</span></label>
          <input
            type="email"
            className="input"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="prenom.nom@kaydangroupe.com"
          />
          <p className="text-2xs text-fg-subtle mt-1">
            L'utilisateur recevra ses identifiants par email à cette adresse.
          </p>
        </div>

        <div>
          <label className="label">Téléphone (E.164)</label>
          <input
            type="tel"
            className="input"
            value={form.phone_e164}
            onChange={(e) => setForm({ ...form, phone_e164: e.target.value })}
            placeholder="+225 07 00 00 00 00"
          />
        </div>

        <div>
          <label className="label">Filiale</label>
          <select
            className="input"
            value={form.subsidiary}
            onChange={(e) => setForm({ ...form, subsidiary: e.target.value })}
          >
            <option value="">— Groupe transverse (pas de filiale) —</option>
            {subsidiaries.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={form.is_executive}
              onChange={(e) => setForm({ ...form, is_executive: e.target.checked })}
              className="rounded accent-copper-500"
            />
            <span><Crown size={11} className="inline mr-1 text-copper-500" /> Membre COMEX</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={form.is_owner}
              onChange={(e) => setForm({ ...form, is_owner: e.target.checked })}
              className="rounded accent-amber-500"
            />
            <span>Owner (DG)</span>
          </label>
        </div>

        <label className="flex items-start gap-2 cursor-pointer text-xs pt-2 border-t border-border">
          <input
            type="checkbox"
            checked={form.send_welcome_email}
            onChange={(e) => setForm({ ...form, send_welcome_email: e.target.checked })}
            className="rounded accent-copper-500 mt-0.5"
          />
          <span className="text-fg-muted">
            Envoyer l'email de bienvenue avec les identifiants (recommandé).
            Décochez uniquement pour les comptes de service ou de test.
          </span>
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <PremiumButton variant="ghost" onClick={() => { reset(); onClose() }}>Annuler</PremiumButton>
          <PremiumButton
            disabled={!emailValid || create.isPending}
            loading={create.isPending}
            onClick={() => create.mutate()}
            iconLeft={<UserPlus size={14} />}
          >
            Créer et envoyer l'email
          </PremiumButton>
        </div>
      </div>
    </Modal>
  )
}


/* ════════════════════════════════════════════════
   Modal de réaffectation
   ════════════════════════════════════════════════ */

function ReassignMemberModal({
  member, onClose, subsidiaries, onSaved,
}: {
  member: MembershipDTO | null
  onClose: () => void
  subsidiaries: Subsidiary[]
  onSaved: () => void
}) {
  const open = !!member
  const [form, setForm] = useState({
    subsidiary: '' as string | '',
    is_executive: false,
    is_owner: false,
    send_email: true,
  })

  // Hydrate à chaque ouverture
  useMemo(() => {
    if (member) {
      setForm({
        subsidiary: member.subsidiary ?? '',
        is_executive: member.is_executive,
        is_owner: member.is_owner,
        send_email: true,
      })
    }
  }, [member])

  const reassign = useMutation({
    mutationFn: () => {
      if (!member) throw new Error('Aucun membership')
      return membersApi.reassign(member.id, {
        subsidiary: form.subsidiary || null,
        is_executive: form.is_executive,
        is_owner: form.is_owner,
        send_email: form.send_email,
      })
    },
    onSuccess: () => {
      toast.success('Affectation mise à jour.' + (form.send_email ? " Email envoyé." : ""))
      onSaved()
      onClose()
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail ?? 'Modification refusée.'),
  })

  if (!member) return null

  return (
    <Modal open={open} onClose={onClose} title={`Affectation — ${member.user_detail.full_name}`}>
      <div className="space-y-4">
        <div className="p-3 rounded-lg bg-bg-subtle border border-border">
          <div className="text-2xs uppercase tracking-wider text-fg-subtle mb-1">Compte</div>
          <div className="text-sm font-medium">{member.user_detail.full_name}</div>
          <div className="text-xs text-fg-muted">{member.user_detail.email}</div>
        </div>

        <div>
          <label className="label">Filiale</label>
          <select
            className="input"
            value={form.subsidiary}
            onChange={(e) => setForm({ ...form, subsidiary: e.target.value })}
          >
            <option value="">— Groupe transverse (pas de filiale) —</option>
            {subsidiaries.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={form.is_executive}
              onChange={(e) => setForm({ ...form, is_executive: e.target.checked })}
              className="rounded accent-copper-500"
            />
            <span><Crown size={11} className="inline mr-1 text-copper-500" /> Membre COMEX</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={form.is_owner}
              onChange={(e) => setForm({ ...form, is_owner: e.target.checked })}
              className="rounded accent-amber-500"
            />
            <span>Owner (DG)</span>
          </label>
        </div>

        <label className="flex items-start gap-2 cursor-pointer text-xs pt-2 border-t border-border">
          <input
            type="checkbox"
            checked={form.send_email}
            onChange={(e) => setForm({ ...form, send_email: e.target.checked })}
            className="rounded accent-copper-500 mt-0.5"
          />
          <span className="text-fg-muted">
            Notifier l'utilisateur du changement d'affectation par email.
          </span>
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <PremiumButton variant="ghost" onClick={onClose}>Annuler</PremiumButton>
          <PremiumButton
            disabled={reassign.isPending}
            loading={reassign.isPending}
            onClick={() => reassign.mutate()}
          >
            Enregistrer
          </PremiumButton>
        </div>
      </div>
    </Modal>
  )
}
