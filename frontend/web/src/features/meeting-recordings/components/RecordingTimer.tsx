import { cn } from '@/utils/cn'

interface Props {
  durationMs: number
  className?: string
  /** Affiche un point rouge clignotant quand `recording` est true. */
  recording?: boolean
}

function format(ms: number): string {
  const sec = Math.floor(ms / 1000)
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function RecordingTimer({ durationMs, recording, className }: Props) {
  return (
    <div className={cn('flex items-center gap-2 font-mono tabular-nums', className)}>
      {recording && (
        <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" aria-hidden />
      )}
      <span>{format(durationMs)}</span>
    </div>
  )
}
