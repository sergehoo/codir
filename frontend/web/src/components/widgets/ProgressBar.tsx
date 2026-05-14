import { cn } from '@/utils/cn'

export function ProgressBar({ value, danger }: { value: number; danger?: boolean }) {
  const v = Math.min(100, Math.max(0, value))
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
        <div className={cn('h-full', danger ? 'bg-rose-500' : 'bg-blue-500')} style={{ width: `${v}%` }} />
      </div>
      <span className="text-xs text-slate-500 tabular w-9 text-right">{v}%</span>
    </div>
  )
}
