import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { AlertTriangle, Clock, ListChecks, Sparkle } from 'lucide-react'

import { notificationsApi, notificationsKeys } from './api'

export function TaskReminderCard() {
  const { data } = useQuery({
    queryKey: notificationsKeys.dashboard(),
    queryFn: () => notificationsApi.dashboardSummary(),
  })
  if (!data) return null

  const cells = [
    { label: 'Ouvertes',    value: data.open_tasks,       tone: 'text-copper-400',  icon: ListChecks },
    { label: 'En retard',   value: data.overdue_tasks,    tone: 'text-danger',      icon: AlertTriangle },
    { label: 'Échéance ≤ 3j', value: data.due_soon_tasks, tone: 'text-warning',     icon: Clock },
    { label: 'Critiques',   value: data.critical_tasks,   tone: 'text-fg',          icon: Sparkle },
  ]

  return (
    <div className="card p-6">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Mes rappels</div>
          <div className="serif text-lg mt-0.5">À traiter aujourd'hui</div>
        </div>
        <Link to="/my-tasks" className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold">
          Mes tâches →
        </Link>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {cells.map((c) => {
          const Icon = c.icon
          return (
            <div key={c.label} className="text-center px-2 py-4 bg-bg-subtle/40 rounded">
              <Icon size={14} className={`mx-auto mb-2 ${c.tone}`} />
              <div className={`serif text-2xl ${c.tone}`}>{c.value}</div>
              <div className="text-[10px] uppercase tracking-widest text-fg-subtle mt-1">{c.label}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
