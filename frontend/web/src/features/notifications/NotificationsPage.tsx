import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { Filter, Inbox, Settings } from 'lucide-react'
import { useState } from 'react'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'

import { notificationsApi, notificationsKeys } from './api'

const EVENTS = [
  { v: '',                          label: 'Tous' },
  { v: 'task_assigned',             label: 'Tâches assignées' },
  { v: 'task_delegated',            label: 'Tâches déléguées' },
  { v: 'task_reminder',             label: 'Rappels' },
  { v: 'task_due_soon',             label: 'Échéances proches' },
  { v: 'task_overdue',              label: 'En retard' },
  { v: 'manager_daily_summary',     label: 'Résumés manager' },
  { v: 'decision_approved',         label: 'Décisions' },
  { v: 'meeting_invited',           label: 'Réunions' },
]

const CHANNELS = [
  { v: '',         label: 'Tous' },
  { v: 'internal', label: 'In-app' },
  { v: 'email',    label: 'Email' },
]

export function NotificationsPage() {
  const qc = useQueryClient()
  const [event, setEvent] = useState('')
  const [channel, setChannel] = useState('')
  const [unreadOnly, setUnreadOnly] = useState(false)

  const params = { event: event || undefined, channel: channel || undefined, unread: unreadOnly }
  const { data, isLoading, error } = useQuery({
    queryKey: notificationsKeys.list(params),
    queryFn: () => notificationsApi.list(params),
  })
  const items = Array.isArray(data) ? data : (data?.results ?? [])

  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationsKeys.all }),
  })
  const markOne = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationsKeys.all }),
  })

  const unread = items.filter((n) => !n.seen_at)

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Inbox"
        title="Notifications"
        description={`${items.length} message(s) · ${unread.length} non lu(s)`}
        actions={
          <div className="flex items-center gap-2">
            <Link to="/notifications/preferences">
              <PremiumButton variant="ghost" size="sm" iconLeft={<Settings size={13} />}>
                Préférences
              </PremiumButton>
            </Link>
            {unread.length > 0 && (
              <PremiumButton variant="secondary" size="sm" onClick={() => markAll.mutate()}>
                Tout marquer lu
              </PremiumButton>
            )}
          </div>
        }
      />

      <section className="px-10 py-5 border-b border-border bg-bg-subtle/20 flex items-center gap-3 flex-wrap">
        <Filter size={14} className="text-fg-subtle" />
        <div className="flex gap-1 flex-wrap">
          {EVENTS.map((e) => (
            <button
              key={e.v} onClick={() => setEvent(e.v)}
              className={`text-2xs uppercase tracking-wider px-3 py-1.5 rounded-md transition font-semibold ${
                event === e.v
                  ? 'bg-copper-500/15 text-copper-400 border border-copper-500/30'
                  : 'text-fg-muted border border-border hover:border-copper-500/30'
              }`}
            >{e.label}</button>
          ))}
        </div>
        <span className="text-fg-subtle text-2xs uppercase tracking-wider mx-2">·</span>
        <div className="flex gap-1">
          {CHANNELS.map((c) => (
            <button
              key={c.v} onClick={() => setChannel(c.v)}
              className={`text-2xs uppercase tracking-wider px-3 py-1.5 rounded-md transition font-semibold ${
                channel === c.v
                  ? 'bg-copper-500/15 text-copper-400 border border-copper-500/30'
                  : 'text-fg-muted border border-border hover:border-copper-500/30'
              }`}
            >{c.label}</button>
          ))}
        </div>
        <span className="text-fg-subtle text-2xs uppercase tracking-wider mx-2">·</span>
        <label className="flex items-center gap-2 text-2xs uppercase tracking-wider text-fg-muted cursor-pointer">
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
          Non lus seulement
        </label>
      </section>

      <section className="px-10 py-8">
        {isLoading && <SkeletonList rows={4} />}

        {!isLoading && error && (
          <div className="card p-12 text-center">
            <Inbox size={28} className="mx-auto text-danger mb-3" strokeWidth={1.5} />
            <p className="text-danger text-sm font-medium">Impossible de charger les notifications.</p>
            <p className="text-fg-muted text-xs mt-2">
              {(error as any)?.response?.status === 401
                ? 'Session expirée — reconnectez-vous.'
                : (error as any)?.message || 'Erreur réseau ou serveur.'}
            </p>
          </div>
        )}

        {!isLoading && !error && items.length === 0 && (
          <div className="card p-12 text-center">
            <Inbox size={28} className="mx-auto text-fg-subtle mb-3" strokeWidth={1.5} />
            <p className="text-fg-muted text-sm">
              {(event || channel || unreadOnly)
                ? 'Aucune notification ne correspond à ces filtres.'
                : 'Vous n\'avez aucune notification pour le moment.'}
            </p>
            {(event || channel || unreadOnly) && (
              <button
                onClick={() => { setEvent(''); setChannel(''); setUnreadOnly(false) }}
                className="mt-3 text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold"
              >
                Réinitialiser les filtres
              </button>
            )}
          </div>
        )}

        {!isLoading && items.length > 0 && (
        <div className="card overflow-hidden">
          <ul className="divide-y divide-border">
            {items.map((n) => (
              <li key={n.id}
                  className={`flex items-start gap-4 p-5 transition hover:bg-fg/[0.04] ${
                    !n.seen_at ? 'bg-copper-500/10 border-l-2 border-l-copper-500' : ''
                  }`}>
                <span className={
                  n.level === 'danger'  ? 'dot-danger mt-2'
                  : n.level === 'warning' ? 'dot-warning mt-2'
                  : n.level === 'success' ? 'dot-success mt-2'
                  : 'dot-copper mt-2'
                } />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-3">
                    <h3 className="font-medium text-sm">{n.title}</h3>
                    {!n.seen_at && <span className="chip-copper">Nouveau</span>}
                    <EmailStatusBadge n={n} />
                    <span className="ml-auto text-2xs uppercase tracking-wider text-fg-subtle">
                      {format(new Date(n.created_at), "d MMM 'à' HH:mm", { locale: fr })}
                    </span>
                  </div>
                  {n.body && (
                    <p className="text-sm text-fg-muted mt-1 leading-relaxed line-clamp-3">{n.body}</p>
                  )}
                  <div className="mt-2 flex items-center gap-3">
                    {(n.action_url || n.link_url) && (
                      <Link to={(n.action_url || n.link_url) as any}
                        onClick={() => !n.seen_at && markOne.mutate(n.id)}
                        className="text-2xs text-copper-400 hover:underline uppercase tracking-wider font-semibold">
                        Ouvrir ↗
                      </Link>
                    )}
                    {!n.seen_at && (
                      <button
                        onClick={() => markOne.mutate(n.id)}
                        className="text-2xs text-fg-muted hover:text-copper-400 uppercase tracking-wider">
                        Marquer lu
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
        )}
      </section>
    </div>
  )
}

function EmailStatusBadge({ n }: { n: any }) {
  if (n.channel !== 'email') return null
  if (n.email_sent_at) return <span className="text-2xs text-success">✉ envoyé</span>
  if (n.failed_at) return <span className="text-2xs text-danger">✉ échec</span>
  if (n.status === 'pending') return <span className="text-2xs text-fg-subtle">✉ en attente</span>
  return null
}
