import { cn } from '@/utils/cn'
import { STATUS_LABELS, type RecordingStatus } from '../types/recording.types'

const COLOR: Record<RecordingStatus, string> = {
  created: 'bg-fg/10 text-fg-muted',
  recording: 'bg-red-500/15 text-red-400 animate-pulse',
  uploading: 'bg-blue-500/15 text-blue-400',
  uploaded: 'bg-blue-500/15 text-blue-400',
  processing: 'bg-blue-500/15 text-blue-400',
  transcribing: 'bg-blue-500/15 text-blue-400',
  diarizing: 'bg-blue-500/15 text-blue-400',
  waiting_speaker_mapping: 'bg-copper-500/15 text-copper-400',
  generating_final_transcript: 'bg-blue-500/15 text-blue-400',
  summarizing: 'bg-blue-500/15 text-blue-400',
  extracting_actions: 'bg-blue-500/15 text-blue-400',
  completed: 'bg-emerald-500/15 text-emerald-400',
  failed: 'bg-red-500/15 text-red-400',
}

interface Props {
  status: RecordingStatus
  className?: string
}

export function RecordingStatusBadge({ status, className }: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
        COLOR[status] || 'bg-fg/10 text-fg-muted',
        className,
      )}
    >
      <span className={cn(
        'w-1.5 h-1.5 rounded-full',
        status === 'recording' ? 'bg-red-400' : 'bg-current opacity-70',
      )} />
      {STATUS_LABELS[status] || status}
    </span>
  )
}
