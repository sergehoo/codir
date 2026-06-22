/**
 * WatchListCard — Top sujets à risque (cockpit prédictif).
 *
 * Lit /dashboard/watchlist/ et affiche jusqu'à 5 items (plans + décisions)
 * triés par criticité. Chaque ligne montre le score, le label, les raisons
 * principales et un lien direct vers la fiche concernée.
 *
 * Pas de bouton Refresh : la query react-query est invalidée automatiquement
 * au switch d'org et toutes les 5min via staleTime.
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { AlertTriangle, ArrowUpRight, ShieldCheck } from 'lucide-react'

import { cn } from '@/utils/cn'

import { dashboardApi, type HealthLabel, type WatchlistItem } from './api'

const LABEL_TONE: Record<HealthLabel, { bg: string; text: string; ring: string }> = {
  healthy:  { bg: 'bg-success/10',  text: 'text-success', ring: 'ring-success/20' },
  watch:    { bg: 'bg-warning/10',  text: 'text-warning', ring: 'ring-warning/20' },
  at_risk:  { bg: 'bg-copper-500/15',text:'text-copper-400',ring:'ring-copper-500/20' },
  critical: { bg: 'bg-danger/10',   text: 'text-danger',  ring: 'ring-danger/25' },
}

const LABEL_FR: Record<HealthLabel, string> = {
  healthy:  'sain',
  watch:    'à surveiller',
  at_risk:  'à risque',
  critical: 'critique',
}

export function WatchListCard({ className }: { className?: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['watchlist', 'cockpit'],
    queryFn: () => dashboardApi.watchlist(10),
    staleTime: 5 * 60_000,
  })

  return (
    <div className={cn('card p-5', className)}>
      <header className="flex items-center justify-between mb-4">
        <div>
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
            Watch list
          </div>
          <h3 className="text-h3 font-semibold mt-0.5">Sujets à risque</h3>
        </div>
        {data && data.count > 0 && (
          <span className="chip chip-copper">{data.count}</span>
        )}
      </header>

      {isLoading && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-12 bg-fg/[0.04] rounded animate-pulse" />
          ))}
        </div>
      )}

      {isError && (
        <div className="text-sm text-fg-muted py-4 text-center">
          Impossible de charger la watch list.
        </div>
      )}

      {!isLoading && !isError && (!data || data.items.length === 0) && (
        <div className="flex flex-col items-center text-center py-8 gap-2">
          <div className="w-12 h-12 rounded-full bg-success/10 grid place-items-center">
            <ShieldCheck size={22} className="text-success" strokeWidth={1.75} />
          </div>
          <div className="text-sm text-fg-muted">
            Aucun sujet à risque actuellement.
          </div>
          <div className="text-2xs text-fg-subtle uppercase tracking-wider">
            Tous les plans et décisions sont sains
          </div>
        </div>
      )}

      {!isLoading && data && data.items.length > 0 && (
        <ul className="divide-y divide-border">
          {data.items.slice(0, 5).map((item) => (
            <WatchListRow key={`${item.kind}-${item.id}`} item={item} />
          ))}
        </ul>
      )}

      {data && data.items.length > 5 && (
        <div className="pt-3 mt-3 border-t border-border text-2xs uppercase tracking-wider text-fg-muted">
          + {data.items.length - 5} autre(s) sujet(s) à risque
        </div>
      )}
    </div>
  )
}


function WatchListRow({ item }: { item: WatchlistItem }) {
  const tone = LABEL_TONE[item.label]

  return (
    <li className="py-3 first:pt-0 last:pb-0 group">
      <Link to={item.url as any} className="flex items-start gap-3 hover:bg-fg/[0.02] -mx-2 px-2 py-1 rounded transition">
        {/* Score */}
        <div className={cn(
          'shrink-0 w-12 h-12 rounded grid place-items-center font-serif text-lg font-medium ring-1',
          tone.bg, tone.text, tone.ring,
        )}>
          {item.score}
        </div>

        {/* Titre + raisons */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-2xs uppercase tracking-wider text-fg-subtle font-semibold">
              {item.kind === 'plan' ? 'Plan' : 'Décision'}
            </span>
            <span className={cn('text-2xs uppercase tracking-wider font-semibold', tone.text)}>
              · {LABEL_FR[item.label]}
            </span>
            {item.priority === 'critical' && (
              <span className="text-2xs uppercase tracking-wider text-danger font-semibold">
                · critique
              </span>
            )}
          </div>
          <div className="text-sm font-medium text-fg truncate mt-0.5">
            {item.title}
          </div>
          {item.reasons.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-fg-muted mt-1">
              <AlertTriangle size={11} className="shrink-0" />
              <span className="truncate">{item.reasons[0]}</span>
              {item.reasons.length > 1 && (
                <span className="text-fg-subtle">+ {item.reasons.length - 1}</span>
              )}
            </div>
          )}
          {item.owner_name && (
            <div className="text-2xs text-fg-subtle uppercase tracking-wider mt-1">
              {item.owner_name}
            </div>
          )}
        </div>

        {/* Chevron */}
        <ArrowUpRight
          size={14}
          className="text-fg-subtle group-hover:text-copper-400 transition shrink-0 mt-1"
        />
      </Link>
    </li>
  )
}
