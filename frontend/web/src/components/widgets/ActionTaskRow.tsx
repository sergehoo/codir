import { format } from 'date-fns'
import { AlertTriangle } from 'lucide-react'

import type { ActionTask } from '@/types'
import { PriorityBadge } from './PriorityBadge'
import { ProgressBar } from './ProgressBar'
import { StatusBadge } from './StatusBadge'

export function ActionTaskRow({ task, onComplete }: { task: ActionTask; onComplete?: (id: string) => void }) {
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="py-3 px-3">
        <div className="flex items-baseline gap-2">
          <span className="font-medium text-sm">{task.title}</span>
          {task.is_overdue && (
            <span className="text-rose-600 inline-flex items-center text-[10px] font-bold">
              <AlertTriangle size={11} /> retard
            </span>
          )}
        </div>
        {task.assignee_detail && (
          <div className="text-xs text-slate-500 mt-0.5">→ {task.assignee_detail.full_name}</div>
        )}
      </td>
      <td className="py-3 px-3"><PriorityBadge priority={task.priority} /></td>
      <td className="py-3 px-3"><StatusBadge status={task.status} /></td>
      <td className="py-3 px-3 text-sm tabular">
        {task.due_date ? format(new Date(task.due_date), 'dd/MM/yyyy') : '—'}
      </td>
      <td className="py-3 px-3"><ProgressBar value={task.progress_percent} /></td>
      <td className="py-3 px-3 text-right">
        {task.status !== 'done' && task.status !== 'cancelled' && onComplete && (
          <button onClick={() => onComplete(task.id)} className="btn-ghost text-xs">Clôturer</button>
        )}
      </td>
    </tr>
  )
}
