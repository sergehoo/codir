// Affichage lecture-seule de la transcription finale (avec noms réels).
import { Clock } from 'lucide-react'

import type { TranscriptSegmentFinal } from '../types/recording.types'

interface Props {
  segments: TranscriptSegmentFinal[]
  emptyLabel?: string
}

function fmt(s: number): string {
  const sec = Math.floor(s)
  const m = Math.floor(sec / 60)
  const r = sec % 60
  return `${m}:${String(r).padStart(2, '0')}`
}

const SPEAKER_COLORS = [
  'text-copper-400 border-copper-500/30 bg-copper-500/5',
  'text-blue-400 border-blue-500/30 bg-blue-500/5',
  'text-emerald-400 border-emerald-500/30 bg-emerald-500/5',
  'text-purple-400 border-purple-500/30 bg-purple-500/5',
  'text-pink-400 border-pink-500/30 bg-pink-500/5',
  'text-amber-400 border-amber-500/30 bg-amber-500/5',
]

export function TranscriptViewer({ segments, emptyLabel }: Props) {
  if (!segments || segments.length === 0) {
    return (
      <div className="p-6 text-sm text-fg-muted text-center border border-border rounded-xl">
        {emptyLabel ?? 'La transcription finale n\'est pas encore disponible.'}
      </div>
    )
  }

  // Map speaker → couleur stable
  const colorMap: Record<string, string> = {}
  const uniques = Array.from(new Set(segments.map((s) => s.speaker)))
  uniques.forEach((sp, i) => {
    colorMap[sp] = SPEAKER_COLORS[i % SPEAKER_COLORS.length]
  })

  return (
    <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-2">
      {segments.map((seg, idx) => (
        <div
          key={idx}
          className="flex items-start gap-3 group"
        >
          <div className={`shrink-0 mt-0.5 px-2 py-0.5 rounded border text-2xs font-medium ${colorMap[seg.speaker]}`}>
            {seg.speaker}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-fg leading-relaxed">{seg.text}</div>
            <div className="flex items-center gap-1 mt-0.5 text-2xs text-fg-subtle opacity-0 group-hover:opacity-100 transition">
              <Clock size={10} /> {fmt(seg.start)} → {fmt(seg.end)}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
