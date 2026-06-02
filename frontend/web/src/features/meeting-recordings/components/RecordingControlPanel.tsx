// Panneau de contrôle d'enregistrement audio — version premium.
//
// Design :
// - Bouton central rouge pulsant pendant l'enregistrement (glow ring).
// - Waveform live 40 barres avec lissage RMS + max-hold visuel.
// - Timer XXL en serif (style chronomètre exécutif).
// - État status à gauche (point qui clignote).
// - Actions secondaires (Pause / Stop) en variant secondary, à droite.
//
// Le composant reste contrôlé par useMediaRecorder — pas de state interne
// sauf la mémorisation des hauteurs max pour le visualiseur (max-hold).
import { Mic, Pause, Play, Square } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { cn } from '@/utils/cn'

import { RecordingTimer } from './RecordingTimer'

interface Props {
  state: 'idle' | 'recording' | 'paused' | 'stopped' | 'error'
  durationMs: number
  audioLevel: number   // 0..1 (RMS lissé)
  onPause: () => void
  onResume: () => void
  onStop: () => void
}

// Nombre de barres dans le visualiseur. Plus c'est élevé, plus c'est fluide
// mais plus c'est coûteux en re-render. 40 = bon compromis 60fps.
const NUM_BARS = 40
const MAX_HOLD_DECAY = 0.97  // décroissance par frame du pic visuel

export function RecordingControlPanel({
  state, durationMs, audioLevel, onPause, onResume, onStop,
}: Props) {
  const isRecording = state === 'recording'
  const isPaused = state === 'paused'

  // Tableau des hauteurs courantes (transmises au DOM via style.height).
  // On utilise un ref pour éviter un setState par frame (60 fois/sec).
  const barsRef = useRef<HTMLSpanElement[]>([])
  const peaksRef = useRef<number[]>(Array(NUM_BARS).fill(0))
  const phaseRef = useRef<number>(0)

  // Animation loop — recalcule les hauteurs à chaque RAF tant qu'on enregistre.
  useEffect(() => {
    let rafId: number | null = null
    const tick = () => {
      // Phase shift visuelle même quand audioLevel=0 (sinon barres figées).
      phaseRef.current = (phaseRef.current + 0.18) % (Math.PI * 2)
      const lvl = isRecording ? audioLevel : 0
      for (let i = 0; i < NUM_BARS; i++) {
        // Mélange : level réel × profil sinusoïdal (donne du caractère)
        // + idle small noise pour que les barres bougent légèrement même au repos
        const sinProfile = 0.5 + 0.5 * Math.sin(phaseRef.current + i * 0.4)
        const noise = isRecording ? (Math.random() * 0.15) : 0
        const target = Math.min(1, lvl * 3.2 * (0.5 + 0.5 * sinProfile) + noise)
        // Max-hold (peak) qui descend doucement = effet "pic flottant"
        const prevPeak = peaksRef.current[i]
        const peak = Math.max(target, prevPeak * MAX_HOLD_DECAY)
        peaksRef.current[i] = peak
        const bar = barsRef.current[i]
        if (bar) {
          const h = isRecording ? 6 + peak * 42 : (isPaused ? 6 + (peaksRef.current[i] * 30) : 4)
          bar.style.height = `${h}px`
          bar.style.opacity = isRecording ? '1' : (isPaused ? '0.5' : '0.3')
        }
      }
      rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)
    return () => { if (rafId) cancelAnimationFrame(rafId) }
  }, [audioLevel, isRecording, isPaused])

  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-bg-elevated to-bg-base shadow-sm">
      {/* Glow effect rouge derrière le bouton central pendant l'enregistrement */}
      {isRecording && (
        <div
          aria-hidden
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-72 h-72 rounded-full bg-red-500/20 blur-3xl pointer-events-none animate-pulse"
        />
      )}

      <div className="relative p-6 sm:p-7">
        {/* Header status + timer */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <span className={cn(
              "w-2 h-2 rounded-full",
              isRecording ? "bg-red-500 animate-pulse"
                          : isPaused ? "bg-amber-400" : "bg-fg/30",
            )} />
            <span className="text-2xs uppercase tracking-[0.2em] font-semibold text-fg-muted">
              {isRecording ? "Enregistrement en cours"
                : isPaused ? "Mise en pause"
                : state === 'error' ? "Erreur"
                : "Prêt à enregistrer"}
            </span>
          </div>
          <RecordingTimer
            durationMs={durationMs}
            recording={isRecording}
            className="text-2xl sm:text-3xl font-mono tabular-nums font-semibold"
          />
        </div>

        {/* Visualiseur waveform — 40 barres animées */}
        <div className="flex items-center justify-center gap-[2px] h-14 mb-6 px-2">
          {Array.from({ length: NUM_BARS }).map((_, i) => (
            <span
              key={i}
              ref={(el) => { if (el) barsRef.current[i] = el }}
              className={cn(
                "w-1 rounded-full transition-colors duration-300",
                isRecording
                  ? "bg-gradient-to-t from-copper-600 via-copper-400 to-copper-300"
                  : isPaused
                    ? "bg-amber-400/70"
                    : "bg-fg/20",
              )}
              style={{ height: '4px' }}
              aria-hidden
            />
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-center gap-3">
          {!isPaused && isRecording && (
            <button
              type="button"
              onClick={onPause}
              className="group flex items-center gap-2 px-5 py-3 rounded-xl border border-border bg-bg-base hover:bg-fg/5 hover:border-fg/20 text-sm font-medium transition-all duration-200"
              aria-label="Mettre l'enregistrement en pause"
            >
              <Pause size={16} className="text-fg-muted group-hover:text-fg transition" />
              Pause
            </button>
          )}
          {isPaused && (
            <button
              type="button"
              onClick={onResume}
              className="group flex items-center gap-2 px-5 py-3 rounded-xl border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-200 text-sm font-semibold transition-all duration-200"
              aria-label="Reprendre l'enregistrement"
            >
              <Play size={16} fill="currentColor" />
              Reprendre
            </button>
          )}

          {/* Bouton central — Mic visuel pour donner du caractère, pas un bouton */}
          <div
            className={cn(
              "relative w-16 h-16 rounded-full grid place-items-center transition-all duration-300",
              isRecording
                ? "bg-gradient-to-br from-red-500 to-red-700 shadow-[0_0_30px_rgba(239,68,68,0.5)]"
                : isPaused
                  ? "bg-gradient-to-br from-amber-400 to-amber-600"
                  : "bg-gradient-to-br from-copper-500 to-copper-700",
            )}
            aria-hidden
          >
            <Mic size={24} className="text-white" strokeWidth={2} />
            {isRecording && (
              <>
                <span className="absolute inset-0 rounded-full border-2 border-red-400/50 animate-ping" />
                <span className="absolute -inset-1 rounded-full border border-red-500/30" />
              </>
            )}
          </div>

          <button
            type="button"
            onClick={onStop}
            className="group flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-br from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white text-sm font-semibold shadow-md shadow-red-500/30 transition-all duration-200"
            aria-label="Arrêter l'enregistrement"
          >
            <Square size={14} fill="currentColor" />
            Arrêter
          </button>
        </div>

        {/* Indication discrète sous les boutons */}
        <div className="mt-4 text-center text-2xs text-fg-subtle tracking-wide">
          {isRecording
            ? "Cliquez sur Arrêter quand la réunion est terminée."
            : isPaused
              ? "L'audio capturé jusqu'ici est conservé. Reprenez pour continuer."
              : null}
        </div>
      </div>
    </div>
  )
}
