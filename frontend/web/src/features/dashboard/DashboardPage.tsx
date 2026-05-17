import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { ArrowUpRight, Calendar, Diamond, Sparkles } from 'lucide-react'

import { AtelierGauge } from '@/components/widgets/AtelierGauge'

import { MasterGauge } from '@/components/widgets/MasterGauge'
import { NeonNumber } from '@/components/widgets/NeonNumber'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { ManagerSummaryWidget } from '@/features/notifications/ManagerSummaryWidget'
import { TaskReminderCard } from '@/features/notifications/TaskReminderCard'
import { useAuthStore } from '@/stores/auth'

import { dashboardApi } from './api'

export function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const accessToken = useAuthStore((s) => s.accessToken)
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', 'beta'],
    queryFn: () => dashboardApi.beta(),
    refetchInterval: 60_000,
    enabled: !!accessToken,
  })
  const { data: epiData } = useQuery({
    queryKey: ['dashboard', 'epi-score'],
    queryFn: () => dashboardApi.epiScore(90),
    refetchInterval: 5 * 60_000,    // toutes les 5 min
    enabled: !!accessToken,
  })
  const k = data?.kpis

  // ── EPI Score : valeur backend si dispo, sinon fallback legacy frontend ──
  const epi = (() => {
    if (epiData?.current?.overall_score !== undefined) {
      return epiData.current.overall_score
    }
    if (!k) return 0
    const open = k.my_tasks_open + k.overdue_tasks + 1
    const ratio = 1 - k.overdue_tasks / open
    return Math.round(60 + ratio * 35)
  })()

  const epiTrend = epiData?.trend
    ? (epiData.trend.delta >= 0
        ? `+${epiData.trend.delta} pts sur 90 j`
        : `${epiData.trend.delta} pts sur 90 j`)
    : ''
  const epiSparkline = epiData?.history?.map((h) => h.score) ?? []
  const epiBreakdown = epiData?.current

  const today = new Date()

  return (
    <div className="min-h-full bg-bg-base text-fg">
      {/* ─── Editorial masthead ───────────────────────────── */}
      <header className="border-b border-border bg-bg-base">
        <div className="px-10 py-8">
          <div className="flex items-center gap-3 text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-5">
            <span className="divider-accent" />
            <span>{format(today, "EEEE d MMMM yyyy", { locale: fr })}</span>
            <span className="dot-muted" />
            <span>Comité de direction</span>
          </div>
          <div className="flex items-end justify-between gap-6 flex-wrap">
            <div>
              <h1 className="serif text-display leading-[1.05] text-fg">
                Bonjour
                {user?.first_name && (
                  <>
                    , <span className="italic text-copper-400">{user.first_name}.</span>
                  </>
                )}
                {!user?.first_name && <>.</>}
              </h1>
              <p className="text-fg-muted mt-3 text-base max-w-2xl">
                Voici la vue consolidée du comité de direction.
              </p>
            </div>
            <PremiumButton variant="secondary" size="md" iconLeft={<Sparkles size={15} />}>
              Briefing du jour
            </PremiumButton>
          </div>
        </div>
      </header>

      {/* ─── KPI Strip ────────────────────────────────────── */}
      <section className="px-10 py-10 border-b border-border">
        <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-6 flex items-center gap-3">
          <span className="divider-accent" /> Indice de Performance
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">

          {/* Master gauge */}
          <div className="lg:col-span-4">
            <MasterGauge
              value={epi}
              label="KPI Score"
              trend={epiTrend || 'Chargement…'}
              breakdown={epiBreakdown}
              sparkline={epiSparkline}
            />
          </div>

          {/* Stats column */}
          <div className="lg:col-span-8 grid grid-cols-2 md:grid-cols-4 gap-8">

            <Stat
              label="Décisions ouvertes"
              value={k?.pending_decisions ?? 0}
              delta={`${k?.approved_decisions ?? 0} validées`}
              to="/decisions"
            />
            <Stat
              label="Projets / Dossiers"
              value={k?.active_plans ?? 0}
              delta={
                (k?.in_progress_meetings ?? 0) > 0
                  ? `${k?.in_progress_meetings} CODIR en cours`
                  : 'en exécution'
              }
              to="/action-plans"
            />
            <Stat
              label="Mes tâches en retard"
              value={k?.my_tasks_overdue ?? 0}
              delta={`${k?.my_tasks_open ?? 0} en cours`}
              warning
              to="/my-tasks"
            />
            <Stat
              label="Retards organisation"
              value={k?.overdue_tasks ?? 0}
              delta={
                (k?.overdue_tasks ?? 0) > 0
                  ? `vue consolidée`
                  : 'aucun retard'
              }
              warning
              to="/live-codir"
            />
          </div>
        </div>
      </section>

      {/* ─── Mes rappels + Suivi manager ──────────────────── */}
      <section className="px-10 py-8 grid grid-cols-1 lg:grid-cols-2 gap-6 border-b border-border">
        <TaskReminderCard />
        <ManagerSummaryWidget />
      </section>

      {/* ─── Trois colonnes : Réunions / Décisions / Notifications ─── */}
      <section className="px-10 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Next session */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
              Prochaine session
            </span>
          </div>

          {data?.upcoming_meetings?.[0] ? (
            <>
              <h3 className="serif text-h1 leading-tight mb-2">
                {data.upcoming_meetings[0].title}
              </h3>
              <div className="flex items-center gap-3 text-sm text-fg-muted mb-6">
                <Calendar size={14} strokeWidth={1.75} />
                <span>{format(new Date(data.upcoming_meetings[0].scheduled_start), "EEEE d MMM 'à' HH:mm", { locale: fr })}</span>
              </div>

              <div className="divider mb-5" />

              {(data?.next_meeting_agenda?.length ?? 0) > 0 ? (
                <ul className="space-y-3 mb-6">
                  {data?.next_meeting_agenda?.map((item, i) => (
                    <li key={item.id} className="flex items-baseline gap-3 text-sm">
                      <span className="text-fg-subtle font-mono text-2xs tabular w-5">
                        {(i + 1).toString().padStart(2, '0')}
                      </span>
                      <span className="flex-1">{item.title}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-fg-subtle text-sm mb-6 italic">
                  Ordre du jour à définir.
                </p>
              )}

              <Link to="/meetings/$id" params={{ id: data.upcoming_meetings[0].id }}>
                <PremiumButton variant="primary" size="md" iconRight={<ArrowUpRight size={15} />} className="w-full">
                  Ouvrir le dossier
                </PremiumButton>
              </Link>
            </>
          ) : (
            <p className="text-fg-subtle text-sm py-12 text-center">Aucune session programmée.</p>
          )}
        </div>

        {/* Decisions à valider */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
              Décisions en attente
            </span>
            <span className="ml-auto chip-copper">{k?.pending_decisions ?? 0}</span>
          </div>

          <div className="space-y-3 divide-y divide-border">
            {(data?.top_pending_decisions ?? []).slice(0, 5).map((d, i) => (
              <Link
                key={d.id}
                to="/decisions/$id" params={{ id: d.id }}
                className="block py-3 group first:pt-0"
              >
                <div className="flex items-start gap-3">
                  <span className="text-fg-subtle font-mono text-2xs tabular pt-1">
                    {(i + 1).toString().padStart(2, '0')}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-fg group-hover:text-copper-400 transition font-medium leading-tight line-clamp-2">
                      {d.title}
                    </div>
                    <div className="text-2xs text-fg-subtle uppercase tracking-wider mt-1.5 flex items-center gap-2">
                      <span>{d.ref}</span>
                      {d.responsible && (
                        <>
                          <span className="dot-muted" />
                          <span className="truncate">{d.responsible}</span>
                        </>
                      )}
                      {d.deadline && (
                        <>
                          <span className="dot-muted" />
                          <span>
                            {format(new Date(d.deadline), 'd MMM', { locale: fr })}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <ArrowUpRight size={14} className="text-fg-subtle group-hover:text-copper-400 transition mt-1" />
                </div>
              </Link>
            ))}
            {(data?.top_pending_decisions?.length ?? 0) === 0 && !isLoading && (
              <div className="text-fg-subtle text-sm py-6 text-center italic">
                Aucune décision en attente.
              </div>
            )}
            {isLoading && <div className="text-fg-subtle text-sm py-3">Chargement…</div>}
          </div>

          <Link to="/decisions" className="btn-link mt-5">
            Voir toutes les décisions <ArrowUpRight size={13} />
          </Link>
        </div>

        {/* Alerts / Activity */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
              Signaux récents
            </span>
            {data?.recent_notifications && data.recent_notifications.length > 0 && (
              <span className="ml-auto chip-quiet">{data.recent_notifications.length}</span>
            )}
          </div>

          <div className="space-y-4">
            {(data?.recent_notifications ?? []).slice(0, 6).map((n) => (
              <div key={n.id} className="flex items-start gap-3">
                <span className={
                  n.level === 'danger'  ? 'dot-danger mt-2'
                  : n.level === 'warning' ? 'dot-warning mt-2'
                  : n.level === 'success' ? 'dot-success mt-2'
                  : 'dot-copper mt-2'
                } />
                <div className="flex-1">
                  <div className="text-sm text-fg font-medium leading-snug">{n.title}</div>
                  {n.body && <div className="text-2xs text-fg-subtle mt-1 leading-relaxed">{n.body}</div>}
                </div>
              </div>
            ))}
            {!isLoading && (data?.recent_notifications?.length ?? 0) === 0 && (
              <div className="text-fg-subtle text-center py-8 flex flex-col items-center gap-2">
                <Diamond size={16} strokeWidth={1.5} />
                <span className="text-sm">Boîte calme.</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ─── Subtle indicators row ─── */}
      <section className="px-10 py-8 border-t border-border bg-bg-subtle/30">
        <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-6 flex items-center gap-3">
          <span className="divider-accent" /> Indicateurs de pilotage
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          <AtelierGauge
            value={Math.round((epi / 100) * 87)}
            max={100}
            label="Taux d'exécution"
            hint="Sur les 90 derniers jours"
          />
          <AtelierGauge
            value={k?.approved_decisions ?? 12}
            max={30}
            label="Vélocité décisionnelle"
            hint="Décisions validées / semaine"
          />
          <AtelierGauge
            value={k?.my_tasks_open ?? 0}
            max={50}
            label="Charge active"
            hint="Tâches ouvertes assignées"
          />
        </div>
      </section>

      <footer className="border-t border-border bg-[#0A0A0A]">
        {/* Bannière Kaydan officielle — fond noir signature */}
        <div className="px-10 py-8 flex items-center justify-between gap-8 flex-wrap">
          <div className="text-2xs text-white/40 uppercase tracking-widest">
            Édité par DATARIUM 
          </div>
          
          <div className="text-2xs text-white/40 uppercase tracking-widest">
            CODIR Executive Platform · {format(today, "yyyy")}
          </div>
        </div>
      </footer>
    </div>
  )
}

function Stat({
  label, value, delta, warning, to,
}: {
  label: string
  value: number
  delta?: string
  warning?: boolean
  /** Si fourni, la card devient cliquable et navigue vers `to`. */
  to?: string
}) {
  const content = (
    <>
      <div className="flex items-center justify-between mb-3">
        <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
          {label}
        </div>
        {to && (
          <ArrowUpRight
            size={13}
            strokeWidth={1.75}
            className="text-fg-subtle group-hover:text-copper-500 transition-colors"
          />
        )}
      </div>
      <div className={`serif ${warning && value > 0 ? 'text-danger' : 'text-fg'} text-kpi leading-none`}>
        <NeonNumber value={value} />
      </div>
      {delta && (
        <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-3">{delta}</div>
      )}
    </>
  )

  if (to) {
    return (
      <Link
        to={to}
        className="group block rounded-lg -m-3 p-3 hover:bg-bg-elevated/50 transition-colors cursor-pointer"
        aria-label={`${label} — voir les détails`}
      >
        {content}
      </Link>
    )
  }
  return <div>{content}</div>
}
