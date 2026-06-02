import { cn } from '@/utils/cn'

interface Props {
  percent: number
  label?: string
  className?: string
}

export function RecordingUploadProgress({ percent, label, className }: Props) {
  const clamped = Math.max(0, Math.min(100, percent))
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-fg-muted">{label ?? 'Upload audio…'}</span>
        <span className="font-mono tabular-nums text-fg">{clamped}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-fg/10 overflow-hidden">
        <div
          className="h-full bg-copper-500 transition-[width] duration-300 ease-out"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
