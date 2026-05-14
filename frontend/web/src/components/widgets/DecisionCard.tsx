import { Link } from '@tanstack/react-router'
import { Lock } from 'lucide-react'

import type { Decision } from '@/types'
import { PriorityBadge } from './PriorityBadge'
import { StatusBadge } from './StatusBadge'

export function DecisionCard({ d }: { d: Decision }) {
  return (
    <Link
      to="/decisions/$id"
      params={{ id: d.id }}
      className="card p-4 hover:border-blue-300 hover:shadow-sm transition block"
    >
      <div className="flex items-baseline gap-2 mb-1">
        <span className="text-xs font-mono text-slate-500 tabular">{d.ref}</span>
        {d.is_confidential && (
          <span className="text-amber-600 inline-flex items-center text-xs">
            <Lock size={11} className="mr-0.5" />
            confidentiel
          </span>
        )}
        <StatusBadge status={d.status} className="ml-auto" />
      </div>
      <div className="font-semibold text-sm leading-snug">{d.title}</div>
      <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
        <PriorityBadge priority={d.priority} />
        {d.responsible_detail && <span>📌 {d.responsible_detail.full_name}</span>}
        {d.deadline && <span>⏰ {new Date(d.deadline).toLocaleDateString('fr-FR')}</span>}
      </div>
    </Link>
  )
}
