/**
 * LogsPage — historique admin des connexions et activités CODIR.
 *
 * Accès : Owner / Staff uniquement (backend = 403 sinon).
 *
 * Deux onglets :
 *  - Connexions (success / failed via django-axes)
 *  - Activités (audit_logs : CRUD métier, login/logout, admin)
 */
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle, Check, ChevronLeft, ChevronRight,
  Globe, LogIn, RefreshCw, ScrollText, Search, ShieldCheck, X,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'
import { StatsBar } from '@/components/widgets/StatsBar'
import { safeShortDateTime } from '@/utils/safeDate'
import { cn } from '@/utils/cn'

import {
  logsApi,
  type AccessLogDTO,
  type AccessLogFilters,
  type AuditLogDTO,
  type AuditLogFilters,
} from './logsApi'

type Tab = 'access' | 'audit'

const PAGE_SIZE = 25

// ─── Mappings ──────────────────────────────────────────────────

const ACTION_LABELS: Record<string, string> = {
  created: 'Création',
  updated: 'Modification',
  deleted: 'Suppression',
  validated: 'Validation',
  approved: 'Approbation',
  closed: 'Clôture',
  started: 'Démarrage',
  completed: 'Terminé',
  cancelled: 'Annulé',
  login: 'Connexion',
  logout: 'Déconnexion',
  login_failed: 'Échec connexion',
  password_reset: 'MDP réinitialisé',
  user_created: 'Compte créé',
  user_deactivated: 'Compte désactivé',
  user_reactivated: 'Compte réactivé',
  user_reassigned: 'Affectation modifiée',
  custom: 'Autre',
}

const ACTION_TONES: Record<string, string> = {
  created: 'bg-success/15 text-success border-success/30',
  updated: 'bg-info/15 text-info border-info/30',
  deleted: 'bg-danger/15 text-danger border-danger/30',
  validated: 'bg-success/15 text-success border-success/30',
  approved: 'bg-success/15 text-success border-success/30',
  closed: 'bg-fg-muted/10 text-fg-muted border-border',
  started: 'bg-copper-400/15 text-copper-400 border-copper-400/30',
  completed: 'bg-success/15 text-success border-success/30',
  cancelled: 'bg-warning/15 text-warning border-warning/30',
  login: 'bg-success/15 text-success border-success/30',
  logout: 'bg-fg-muted/10 text-fg-muted border-border',
  login_failed: 'bg-danger/15 text-danger border-danger/30',
  password_reset: 'bg-warning/15 text-warning border-warning/30',
  user_created: 'bg-info/15 text-info border-info/30',
  user_deactivated: 'bg-warning/15 text-warning border-warning/30',
  user_reactivated: 'bg-success/15 text-success border-success/30',
  user_reassigned: 'bg-info/15 text-info border-info/30',
  custom: 'bg-fg-muted/10 text-fg-muted border-border',
}

function ActionBadge({ action }: { action: string }) {
  const tone = ACTION_TONES[action] ?? ACTION_TONES.custom
  const label = ACTION_LABELS[action] ?? action
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold uppercase tracking-wider border',
      tone,
    )}>
      {label}
    </span>
  )
}

function shortUA(ua: string): string {
  if (!ua) return '—'
  const m = ua.match(/(Chrome|Firefox|Safari|Edge|Opera)\/[\d.]+/i)
  const os = ua.match(/(Windows|Mac OS X|Linux|Android|iPhone|iPad)/i)
  const parts = [m?.[0]?.split('/')[0], os?.[0]].filter(Boolean)
  return parts.join(' · ') || ua.slice(0, 40)
}

// ─── Page ──────────────────────────────────────────────────────

export function LogsPage() {
  const [tab, setTab] = useState<Tab>('access')

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Paramètres · Sécurité"
        title="Journal d'activité"
        description="Historique complet des connexions et des actions effectuées sur la plateforme. Réservé aux administrateurs."
      />

      <section className="px-10 pt-6">
        <div className="flex gap-1 border-b border-border">
          <TabButton
            active={tab === 'access'}
            onClick={() => setTab('access')}
            icon={<LogIn size={14} />}
          >
            Connexions
          </TabButton>
          <TabButton
            active={tab === 'audit'}
            onClick={() => setTab('audit')}
            icon={<ScrollText size={14} />}
          >
            Activités
          </TabButton>
        </div>
      </section>

      {tab === 'access' ? <AccessLogsPanel /> : <AuditLogsPanel />}
    </div>
  )
}

function TabButton({
  active, onClick, icon, children,
}: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
        active
          ? 'border-copper-400 text-copper-400'
          : 'border-transparent text-fg-muted hover:text-fg-default',
      )}
    >
      {icon}
      {children}
    </button>
  )
}

// ─── Onglet : Connexions ───────────────────────────────────────

function AccessLogsPanel() {
  const [filters, setFilters] = useState<AccessLogFilters>({ page: 1, limit: PAGE_SIZE })

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['settings', 'logs', 'access', filters],
    queryFn: () => logsApi.listAccessLogs(filters),
    placeholderData: (prev) => prev,
  })

  const list = data?.results ?? []
  const stats = useMemo(() => ({
    total: data?.count ?? 0,
    success: list.filter((r) => r.kind === 'success').length,
    failed: list.filter((r) => r.kind === 'failed').length,
  }), [data, list])

  const setField = <K extends keyof AccessLogFilters>(k: K, v: AccessLogFilters[K]) =>
    setFilters((f) => ({ ...f, [k]: v, page: 1 }))

  return (
    <>
      <section className="px-10 pt-6">
        <StatsBar items={[
          { label: 'Évènements (page)', value: stats.total, tone: 'copper' },
          { label: 'Réussites', value: stats.success, tone: 'success' },
          { label: 'Échecs', value: stats.failed, tone: 'danger' },
        ]} />
      </section>

      <section className="px-10 py-6">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="relative flex-1 max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
            <input
              id="access-search"
              name="access-search"
              type="text"
              value={filters.username ?? ''}
              onChange={(e) => setField('username', e.target.value)}
              placeholder="Filtrer par email (exact)…"
              className="w-full pl-9 pr-3 py-2 rounded-md bg-bg-elevated border border-border text-sm"
            />
          </div>
          <select
            id="access-kind"
            name="access-kind"
            value={filters.kind ?? ''}
            onChange={(e) => setField('kind', e.target.value as AccessLogFilters['kind'])}
            className="bg-bg-elevated border border-border rounded-md px-3 py-2 text-sm"
          >
            <option value="">Tout type</option>
            <option value="success">Réussites</option>
            <option value="failed">Échecs</option>
          </select>
          <input
            id="access-from"
            name="access-from"
            type="date"
            value={filters.date_from ?? ''}
            onChange={(e) => setField('date_from', e.target.value)}
            className="bg-bg-elevated border border-border rounded-md px-3 py-2 text-sm"
          />
          <input
            id="access-to"
            name="access-to"
            type="date"
            value={filters.date_to ?? ''}
            onChange={(e) => setField('date_to', e.target.value)}
            className="bg-bg-elevated border border-border rounded-md px-3 py-2 text-sm"
          />
          {(filters.username || filters.kind || filters.date_from || filters.date_to) && (
            <button
              onClick={() => setFilters({ page: 1, limit: PAGE_SIZE })}
              className="inline-flex items-center gap-1 text-xs text-copper-400 hover:underline"
            >
              <X size={12} /> Réinitialiser
            </button>
          )}
          <div className="flex-1" />
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 text-xs text-fg-muted hover:text-fg-default disabled:opacity-50"
            title="Recharger"
          >
            <RefreshCw size={12} className={cn(isFetching && 'animate-spin')} />
            Actualiser
          </button>
        </div>

        {isLoading && <SkeletonList rows={6} />}

        {!isLoading && error && (
          <ErrorBlock error={error} />
        )}

        {!isLoading && !error && list.length === 0 && (
          <EmptyBlock
            icon={<LogIn size={28} />}
            text="Aucune connexion correspondant aux filtres."
          />
        )}

        {list.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-border bg-bg-elevated">
            <table className="w-full text-sm">
              <thead className="bg-bg-base text-2xs uppercase tracking-widest text-fg-muted">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold w-32">Type</th>
                  <th className="text-left px-4 py-3 font-semibold">Utilisateur</th>
                  <th className="text-left px-4 py-3 font-semibold">IP</th>
                  <th className="text-left px-4 py-3 font-semibold">Navigateur</th>
                  <th className="text-left px-4 py-3 font-semibold w-44">Date / heure</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.map((r, i) => <AccessRow key={`${r.attempt_time}-${i}`} row={r} />)}
              </tbody>
            </table>
          </div>
        )}

        <PaginationBar
          page={filters.page ?? 1}
          hasNext={!!data?.next}
          hasPrev={!!data?.previous}
          totalCount={data?.count ?? 0}
          pageSize={PAGE_SIZE}
          onPrev={() => setFilters((f) => ({ ...f, page: Math.max(1, (f.page ?? 1) - 1) }))}
          onNext={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
        />
      </section>
    </>
  )
}

function AccessRow({ row }: { row: AccessLogDTO }) {
  const isOk = row.kind === 'success'
  return (
    <tr className="hover:bg-bg-base/50">
      <td className="px-4 py-3">
        <span className={cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded text-2xs font-semibold uppercase tracking-wider border',
          isOk ? 'bg-success/15 text-success border-success/30'
               : 'bg-danger/15 text-danger border-danger/30',
        )}>
          {isOk ? <Check size={10} /> : <AlertTriangle size={10} />}
          {isOk ? 'Succès' : 'Échec'}
        </span>
        {!isOk && row.failures_since_start !== null && row.failures_since_start > 1 && (
          <div className="text-2xs text-warning mt-1">
            {row.failures_since_start} tentatives
          </div>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="font-medium text-fg-default">{row.user_full_name || row.username || '—'}</div>
        {row.user_full_name && row.username && (
          <div className="text-2xs text-fg-muted">{row.username}</div>
        )}
      </td>
      <td className="px-4 py-3 text-fg-muted font-mono text-xs">
        <span className="inline-flex items-center gap-1">
          <Globe size={11} /> {row.ip_address || '—'}
        </span>
      </td>
      <td className="px-4 py-3 text-fg-muted text-xs" title={row.user_agent}>
        {shortUA(row.user_agent)}
      </td>
      <td className="px-4 py-3 text-fg-muted text-xs whitespace-nowrap">
        {safeShortDateTime(row.attempt_time)}
      </td>
    </tr>
  )
}

// ─── Onglet : Activités ────────────────────────────────────────

function AuditLogsPanel() {
  const [filters, setFilters] = useState<AuditLogFilters>({ page: 1, limit: PAGE_SIZE })

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['settings', 'logs', 'audit', filters],
    queryFn: () => logsApi.listAuditLogs(filters),
    placeholderData: (prev) => prev,
  })

  const list = data?.results ?? []
  const stats = useMemo(() => ({
    total: data?.count ?? 0,
    logins: list.filter((r) => r.action === 'login').length,
    failed: list.filter((r) => r.action === 'login_failed').length,
    admin: list.filter((r) => r.action.startsWith('user_') || r.action === 'password_reset').length,
  }), [data, list])

  const setField = <K extends keyof AuditLogFilters>(k: K, v: AuditLogFilters[K]) =>
    setFilters((f) => ({ ...f, [k]: v, page: 1 }))

  return (
    <>
      <section className="px-10 pt-6">
        <StatsBar items={[
          { label: 'Événements (total)', value: stats.total, tone: 'copper' },
          { label: 'Connexions', value: stats.logins, tone: 'success' },
          { label: 'Échecs login', value: stats.failed, tone: 'danger' },
          { label: 'Actions admin', value: stats.admin, tone: 'info' },
        ]} />
      </section>

      <section className="px-10 py-6">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="relative flex-1 max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
            <input
              id="audit-search"
              name="audit-search"
              type="text"
              value={filters.search ?? ''}
              onChange={(e) => setField('search', e.target.value)}
              placeholder="Rechercher (description, cible, auteur)…"
              className="w-full pl-9 pr-3 py-2 rounded-md bg-bg-elevated border border-border text-sm"
            />
          </div>
          <select
            id="audit-action"
            name="audit-action"
            value={filters.action ?? ''}
            onChange={(e) => setField('action', e.target.value)}
            className="bg-bg-elevated border border-border rounded-md px-3 py-2 text-sm min-w-[180px]"
          >
            <option value="">Toute action</option>
            {Object.entries(ACTION_LABELS).map(([k, label]) => (
              <option key={k} value={k}>{label}</option>
            ))}
          </select>
          <input
            id="audit-from"
            name="audit-from"
            type="date"
            value={filters.date_from ?? ''}
            onChange={(e) => setField('date_from', e.target.value)}
            className="bg-bg-elevated border border-border rounded-md px-3 py-2 text-sm"
          />
          <input
            id="audit-to"
            name="audit-to"
            type="date"
            value={filters.date_to ?? ''}
            onChange={(e) => setField('date_to', e.target.value)}
            className="bg-bg-elevated border border-border rounded-md px-3 py-2 text-sm"
          />
          {(filters.search || filters.action || filters.date_from || filters.date_to) && (
            <button
              onClick={() => setFilters({ page: 1, limit: PAGE_SIZE })}
              className="inline-flex items-center gap-1 text-xs text-copper-400 hover:underline"
            >
              <X size={12} /> Réinitialiser
            </button>
          )}
          <div className="flex-1" />
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 text-xs text-fg-muted hover:text-fg-default disabled:opacity-50"
          >
            <RefreshCw size={12} className={cn(isFetching && 'animate-spin')} />
            Actualiser
          </button>
        </div>

        {isLoading && <SkeletonList rows={6} />}
        {!isLoading && error && <ErrorBlock error={error} />}
        {!isLoading && !error && list.length === 0 && (
          <EmptyBlock
            icon={<ScrollText size={28} />}
            text="Aucune activité correspondant aux filtres."
          />
        )}

        {list.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-border bg-bg-elevated">
            <table className="w-full text-sm">
              <thead className="bg-bg-base text-2xs uppercase tracking-widest text-fg-muted">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold w-44">Action</th>
                  <th className="text-left px-4 py-3 font-semibold">Auteur</th>
                  <th className="text-left px-4 py-3 font-semibold">Description</th>
                  <th className="text-left px-4 py-3 font-semibold">IP</th>
                  <th className="text-left px-4 py-3 font-semibold w-44">Date / heure</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.map((r) => <AuditRow key={r.id} row={r} />)}
              </tbody>
            </table>
          </div>
        )}

        <PaginationBar
          page={filters.page ?? 1}
          hasNext={!!data?.next}
          hasPrev={!!data?.previous}
          totalCount={data?.count ?? 0}
          pageSize={PAGE_SIZE}
          onPrev={() => setFilters((f) => ({ ...f, page: Math.max(1, (f.page ?? 1) - 1) }))}
          onNext={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
        />
      </section>
    </>
  )
}

function AuditRow({ row }: { row: AuditLogDTO }) {
  const actor = row.actor_detail
  return (
    <tr className="hover:bg-bg-base/50">
      <td className="px-4 py-3">
        <ActionBadge action={row.action} />
        {row.target_model && (
          <div className="text-2xs text-fg-muted mt-1 font-mono">{row.target_model}</div>
        )}
      </td>
      <td className="px-4 py-3">
        {actor ? (
          <div>
            <div className="font-medium text-fg-default">{actor.full_name || actor.email}</div>
            <div className="text-2xs text-fg-muted">{actor.email}</div>
          </div>
        ) : (
          <span className="text-fg-muted text-xs italic">Système</span>
        )}
      </td>
      <td className="px-4 py-3 text-fg-default text-xs max-w-md">
        <div className="line-clamp-2" title={row.description}>
          {row.description || row.target_repr || '—'}
        </div>
        {row.target_repr && row.description && (
          <div className="text-2xs text-fg-muted mt-0.5 truncate" title={row.target_repr}>
            cible : {row.target_repr}
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-fg-muted font-mono text-xs">
        {row.ip || '—'}
      </td>
      <td className="px-4 py-3 text-fg-muted text-xs whitespace-nowrap">
        {safeShortDateTime(row.created_at)}
      </td>
    </tr>
  )
}

// ─── Shared blocks ─────────────────────────────────────────────

function ErrorBlock({ error }: { error: unknown }) {
  const status = (error as any)?.response?.status
  const msg = status === 403
    ? "Vous n'avez pas la permission de consulter les logs (admin requis)."
    : status === 401
      ? 'Session expirée — reconnectez-vous.'
      : (error as any)?.message || 'Erreur réseau ou serveur.'
  return (
    <div className="card p-12 text-center">
      <ShieldCheck size={28} className="mx-auto text-danger mb-3" strokeWidth={1.5} />
      <p className="text-danger text-sm font-medium">Impossible de charger les logs.</p>
      <p className="text-fg-muted text-xs mt-2">{msg}</p>
    </div>
  )
}

function EmptyBlock({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="card p-12 text-center">
      <div className="mx-auto text-fg-subtle mb-3" >{icon}</div>
      <p className="text-fg-muted text-sm">{text}</p>
    </div>
  )
}

function PaginationBar({
  page, hasNext, hasPrev, totalCount, pageSize, onPrev, onNext,
}: {
  page: number; hasNext: boolean; hasPrev: boolean; totalCount: number;
  pageSize: number; onPrev: () => void; onNext: () => void;
}) {
  if (totalCount <= pageSize && page === 1) return null
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))
  return (
    <div className="flex items-center justify-between mt-4 text-xs text-fg-muted">
      <div>
        {totalCount.toLocaleString('fr-FR')} évènement{totalCount > 1 ? 's' : ''} —
        page {page} / {totalPages}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onPrev}
          disabled={!hasPrev}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded border border-border bg-bg-elevated disabled:opacity-40 disabled:cursor-not-allowed hover:bg-bg-base"
        >
          <ChevronLeft size={12} /> Précédent
        </button>
        <button
          onClick={onNext}
          disabled={!hasNext}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded border border-border bg-bg-elevated disabled:opacity-40 disabled:cursor-not-allowed hover:bg-bg-base"
        >
          Suivant <ChevronRight size={12} />
        </button>
      </div>
    </div>
  )
}
