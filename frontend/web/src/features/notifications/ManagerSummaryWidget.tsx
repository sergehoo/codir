import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BarChart3, ChevronRight } from 'lucide-react'

import { notificationsApi, notificationsKeys } from './api'

export function ManagerSummaryWidget() {
  const { data } = useQuery({
    queryKey: notificationsKeys.dashboard(),
    queryFn: () => notificationsApi.dashboardSummary(),
  })
  const summary = data?.manager_summary
  const scope = data?.manager_scope

  if (!summary || !scope) return null

  const stats = [
    { label: 'Ouvertes',   value: summary.open,         tone: 'text-copper-400' },
    { label: 'En retard',  value: summary.overdue,      tone: 'text-danger' },
    { label: 'Critiques',  value: summary.critical,     tone: 'text-warning' },
    { label: 'Bloquées',   value: summary.blocked,      tone: 'text-fg-muted' },
    { label: 'Avancement', value: `${summary.progress_avg}%`, tone: 'text-fg' },
  ]

  const scopeLabel = scope.direction || scope.subsidiary || 'Mon périmètre'

  return (
    <div className="card p-6">
      <div className="flex items-baseline justify-between mb-4">
        <div className="flex items-center gap-3">
          <BarChart3 size={14} className="text-copper-400" />
          <div>
            <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Suivi manager</div>
            <div className="serif text-lg mt-0.5">{scopeLabel}</div>
          </div>
        </div>
        <div className="text-2xs text-fg-subtle uppercase tracking-wider">
          {summary.decisions_pending} décision(s) en attente
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3 mb-5">
        {stats.map((s) => (
          <div key={s.label} className="text-center px-2 py-3 bg-bg-subtle/40 rounded">
            <div className={`serif text-2xl ${s.tone}`}>{s.value}</div>
            <div className="text-[10px] uppercase tracking-widest text-fg-subtle mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {summary.top_tasks?.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-2">
            Top {summary.top_tasks.length} prioritaires
          </div>
          {summary.top_tasks.slice(0, 5).map((t) => (
            <div key={t.id} className="flex items-center gap-3 px-3 py-2 bg-bg-subtle/30 rounded text-sm hover:bg-fg/[0.04] transition">
              <span className="flex-1 truncate">{t.title}</span>
              {t.due_date && <span className="text-2xs text-fg-subtle tabular">{t.due_date}</span>}
              {t.priority === 'critical' && <AlertTriangle size={12} className="text-danger" />}
              <ChevronRight size={12} className="text-fg-subtle" />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
