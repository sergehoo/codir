// Panneau de contrôle audio : Pause / Reprendre / Arrêter + niveau audio.
// Utilise le state retourné par useMediaRecorder.
import { Mic, Pause, Play, Square } from 'lucide-react'

import { cn } from '@/utils/cn'

import { RecordingTimer } from './RecordingTimer'

interface Props {
  state: 'idle' | 'recording' | 'paused' | 'stopped' | 'error'
  durationMs: number
  audioLevel: number
  onPause: () => void
  onResume: () => void
  onStop: () => void
}

export function RecordingControlPanel({
  state, durationMs, audioLevel, onPause, onResume, onStop,
}: Props) {
  const isRecording = state === 'recording'
  const isPaused = state === 'paused'

  // 12 barres pour la viz audio — plus le rms est haut, plus de barres allumées
  const bars = 12
  const lit = Math.min(bars, Math.round(audioLevel * bars * 3))

  return (
    <div
      className="flex items-center gap-4 p-4 rounded-xl border border-border bg-bg-elevated shadow-sm"
      role="region"
      aria-label="Contrôle de l'enregistrement"
    >
      <div className="flex items-center gap-3">
        <div className={cn(
          'w-10 h-10 rounded-full grid place-items-center transition-colors',
          isRecording ? 'bg-red-500/15 text-red-400' : 'bg-fg/10 text-fg-muted',
        )}>
          <Mic size={18} />
        </div>
        <div className="flex flex-col">
          <RecordingTimer durationMs={durationMs} recording={isRecording} className="text-base font-semibold" />
          <span className="text-2xs uppercase tracking-wider text-fg-subtle">
            {isRecording ? 'Enregistrement' : isPaused ? 'En pause' : 'Prêt'}
          </span>
        </div>
      </div>

      {/* Visualiseur niveau audio */}
      <div
        className="flex items-end gap-0.5 h-7 ml-2"
        aria-label="Niveau audio"
      >
        {Array.from({ length: bars }).map((_, i) => {
          const on = i < lit
          const height = 30 + i * 4
          return (
            <span
              key={i}
              className={cn(
                'w-1 rounded-sm transition-all duration-100',
                on ? 'bg-copper-500' : 'bg-fg/15',
              )}
              style={{ height: `${Math.min(28, height)}px` }}
            />
          )
        })}
      </div>

      <div className="flex-1" />

      {/* Pause / Reprendre */}
      {isRecording && (
        <button
          type="button"
          onClick={onPause}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-border bg-bg-base hover:bg-fg/5 text-sm font-medium transition"
        >
          <Pause size={14} /> Pause
        </button>
      )}
      {isPaused && (
        <button
          type="button"
          onClick={onResume}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-border bg-bg-base hover:bg-fg/5 text-sm font-medium transition"
        >
          <Play size={14} /> Reprendre
        </button>
      )}

      {/* Stop */}
      <button
        type="button"
        onClick={onStop}
        className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-semibold transition"
      >
        <Square size={14} fill="white" /> Arrêter
      </button>
    </div>
  )
}
