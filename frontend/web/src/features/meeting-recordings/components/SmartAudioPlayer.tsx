// SmartAudioPlayer — lecteur audio premium réutilisable.
//
// Features :
// - Waveform statique en canvas (échantillonné via Web Audio API au chargement).
// - Barre de progression cliquable + glissable.
// - Skip ±5s.
// - Vitesse de lecture 1× / 1.25× / 1.5× / 2×.
// - Raccourcis clavier (focus le composant) : Space = play/pause, ←/→ = skip 5s.
// - Affichage temps courant / total.
//
// Optimisation : la waveform est calculée 1× au mount, mémoïsée. Si le fichier
// est gros (>5 Mo), on skip l'analyse pour éviter de bloquer l'UI.
import { Loader2, Pause, Play, Rewind, FastForward, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { cn } from '@/utils/cn'

interface Props {
  url: string
  label?: string
  /** Compact = hauteur réduite, pas de raccourcis clavier (cards). */
  compact?: boolean
  className?: string
}

type Speed = 1 | 1.25 | 1.5 | 2
const SPEEDS: Speed[] = [1, 1.25, 1.5, 2]
const WAVEFORM_BUCKETS = 80  // nombre de pics affichés

function fmt(s: number): string {
  if (!s || !isFinite(s)) return '0:00'
  const sec = Math.floor(s)
  const m = Math.floor(sec / 60)
  return `${m}:${String(sec % 60).padStart(2, '0')}`
}

/**
 * Échantillonne un AudioBuffer en N buckets (pics RMS) pour le rendu canvas.
 * Renvoie un Float32Array de N valeurs entre 0 et 1.
 */
async function computeWaveform(url: string, buckets: number): Promise<Float32Array | null> {
  try {
    const Ctx = window.AudioContext || (window as any).webkitAudioContext
    if (!Ctx) return null
    const res = await fetch(url, { credentials: 'omit' })
    if (!res.ok) return null
    const buf = await res.arrayBuffer()
    if (buf.byteLength > 20 * 1024 * 1024) return null  // skip > 20 Mo
    const ctx = new Ctx()
    try {
      const audio = await ctx.decodeAudioData(buf)
      const channel = audio.getChannelData(0)
      const samplesPerBucket = Math.floor(channel.length / buckets)
      const peaks = new Float32Array(buckets)
      let max = 0
      for (let b = 0; b < buckets; b++) {
        let sum = 0
        const start = b * samplesPerBucket
        const end = start + samplesPerBucket
        for (let i = start; i < end; i++) {
          sum += channel[i] * channel[i]
        }
        peaks[b] = Math.sqrt(sum / samplesPerBucket)
        if (peaks[b] > max) max = peaks[b]
      }
      // Normalise sur [0, 1] avec un floor mini pour qu'on voie qqch même sur audio faible
      if (max > 0) {
        for (let b = 0; b < buckets; b++) {
          peaks[b] = Math.max(0.05, peaks[b] / max)
        }
      }
      return peaks
    } finally {
      try { ctx.close() } catch { /* ignore */ }
    }
  } catch {
    return null
  }
}

export function SmartAudioPlayer({ url, label, compact = false, className }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)

  const [playing, setPlaying] = useState(false)
  const [current, setCurrent] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState<Speed>(1)
  const [peaks, setPeaks] = useState<Float32Array | null>(null)
  const [loadingPeaks, setLoadingPeaks] = useState(true)
  const [dragging, setDragging] = useState(false)

  // Calcul waveform au mount + au changement d'URL
  useEffect(() => {
    let cancelled = false
    setLoadingPeaks(true)
    setPeaks(null)
    computeWaveform(url, WAVEFORM_BUCKETS).then((p) => {
      if (!cancelled) {
        setPeaks(p)
        setLoadingPeaks(false)
      }
    })
    return () => { cancelled = true }
  }, [url])

  // Synchro audio events → state React
  useEffect(() => {
    const a = audioRef.current
    if (!a) return
    const onTime = () => { if (!dragging) setCurrent(a.currentTime) }
    const onMeta = () => setDuration(a.duration || 0)
    const onEnd = () => { setPlaying(false); setCurrent(0) }
    a.addEventListener('timeupdate', onTime)
    a.addEventListener('loadedmetadata', onMeta)
    a.addEventListener('ended', onEnd)
    return () => {
      a.removeEventListener('timeupdate', onTime)
      a.removeEventListener('loadedmetadata', onMeta)
      a.removeEventListener('ended', onEnd)
    }
  }, [dragging])

  // Dessine la waveform sur le canvas
  useEffect(() => {
    const cvs = canvasRef.current
    if (!cvs) return
    const ctx = cvs.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    const w = cvs.clientWidth
    const h = cvs.clientHeight
    cvs.width = Math.floor(w * dpr)
    cvs.height = Math.floor(h * dpr)
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, w, h)

    // Si pas de peaks (loading ou skip), affiche des barres statiques fades
    const data = peaks || new Float32Array(WAVEFORM_BUCKETS).fill(0.3)
    const barW = (w / data.length) * 0.7
    const barGap = (w / data.length) * 0.3
    const progress = duration > 0 ? current / duration : 0
    const playedX = w * progress

    for (let i = 0; i < data.length; i++) {
      const x = i * (barW + barGap)
      const peak = data[i]
      const barH = Math.max(2, peak * h * 0.85)
      const y = (h - barH) / 2
      const isPlayed = x < playedX
      ctx.fillStyle = isPlayed
        ? '#B8693C'  // copper-500 — partie jouée
        : 'rgba(184,105,60,0.25)'  // copper transparent — pas encore joué
      ctx.fillRect(x, y, barW, barH)
    }
  }, [peaks, current, duration])

  // Re-render canvas au resize
  useEffect(() => {
    const cvs = canvasRef.current
    if (!cvs) return
    const ro = new ResizeObserver(() => {
      // Force re-paint en mettant à jour current (qui re-trigger l'effect ci-dessus)
      setCurrent((c) => c)
    })
    ro.observe(cvs)
    return () => ro.disconnect()
  }, [])

  const toggle = useCallback(() => {
    const a = audioRef.current
    if (!a) return
    if (playing) {
      a.pause(); setPlaying(false)
    } else {
      a.playbackRate = speed
      a.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
    }
  }, [playing, speed])

  const skip = useCallback((delta: number) => {
    const a = audioRef.current
    if (!a) return
    a.currentTime = Math.max(0, Math.min(a.duration || 0, a.currentTime + delta))
    setCurrent(a.currentTime)
  }, [])

  const setRate = (s: Speed) => {
    setSpeed(s)
    const a = audioRef.current
    if (a) a.playbackRate = s
  }

  // Click/drag sur la waveform pour seek
  const handleSeek = useCallback((clientX: number) => {
    const cvs = canvasRef.current
    const a = audioRef.current
    if (!cvs || !a || !a.duration) return
    const rect = cvs.getBoundingClientRect()
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    a.currentTime = pct * a.duration
    setCurrent(a.currentTime)
  }, [])

  // Raccourcis clavier (uniquement quand le composant a le focus, pas compact)
  useEffect(() => {
    if (compact) return
    const handler = (e: KeyboardEvent) => {
      if (!containerRef.current?.contains(document.activeElement)) return
      if (e.code === 'Space') { e.preventDefault(); toggle() }
      else if (e.code === 'ArrowLeft') { e.preventDefault(); skip(-5) }
      else if (e.code === 'ArrowRight') { e.preventDefault(); skip(5) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [toggle, skip, compact])

  return (
    <div
      ref={containerRef}
      tabIndex={compact ? -1 : 0}
      className={cn(
        'group rounded-xl border border-border bg-bg-elevated overflow-hidden focus:outline-none focus:ring-2 focus:ring-copper-500/40 focus:ring-offset-1 focus:ring-offset-bg-base',
        compact ? 'p-2.5' : 'p-3.5',
        className,
      )}
    >
      <div className={cn('flex items-center gap-3', compact && 'gap-2.5')}>
        {/* Play / Pause */}
        <button
          type="button"
          onClick={toggle}
          className={cn(
            'shrink-0 rounded-full grid place-items-center transition-all duration-200',
            compact ? 'w-9 h-9' : 'w-11 h-11',
            playing
              ? 'bg-gradient-to-br from-copper-500 to-copper-700 text-white shadow-md shadow-copper-500/30'
              : 'bg-fg/10 text-fg hover:bg-fg/20',
          )}
          aria-label={playing ? 'Pause' : 'Lire'}
        >
          {playing
            ? <Pause size={compact ? 14 : 16} fill="currentColor" />
            : <Play size={compact ? 14 : 16} fill="currentColor" className="ml-0.5" />}
        </button>

        {/* Waveform + temps */}
        <div className="flex-1 min-w-0">
          {label && !compact && (
            <div className="text-2xs uppercase tracking-wider text-fg-subtle mb-1">
              {label}
            </div>
          )}
          <div className="relative">
            <canvas
              ref={canvasRef}
              className={cn(
                'block w-full cursor-pointer',
                compact ? 'h-7' : 'h-10',
              )}
              onMouseDown={(e) => { setDragging(true); handleSeek(e.clientX) }}
              onMouseMove={(e) => { if (dragging) handleSeek(e.clientX) }}
              onMouseUp={() => setDragging(false)}
              onMouseLeave={() => setDragging(false)}
              onTouchStart={(e) => { setDragging(true); handleSeek(e.touches[0].clientX) }}
              onTouchMove={(e) => { if (dragging) handleSeek(e.touches[0].clientX) }}
              onTouchEnd={() => setDragging(false)}
              aria-label="Barre de progression — cliquez pour naviguer"
            />
            {loadingPeaks && !peaks && (
              <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-fg-subtle">
                <Loader2 size={12} className="animate-spin" />
              </span>
            )}
          </div>
        </div>

        {/* Temps + contrôles secondaires */}
        <div className="shrink-0 flex items-center gap-2">
          <span className="text-2xs font-mono tabular-nums text-fg-muted whitespace-nowrap">
            {fmt(current)} / {fmt(duration)}
          </span>
          {!compact && (
            <>
              <button
                type="button"
                onClick={() => skip(-5)}
                className="p-1.5 rounded text-fg-muted hover:text-fg hover:bg-fg/5 transition"
                aria-label="Reculer de 5 secondes"
                title="−5s (←)"
              >
                <Rewind size={13} />
              </button>
              <button
                type="button"
                onClick={() => skip(5)}
                className="p-1.5 rounded text-fg-muted hover:text-fg hover:bg-fg/5 transition"
                aria-label="Avancer de 5 secondes"
                title="+5s (→)"
              >
                <FastForward size={13} />
              </button>
              <button
                type="button"
                onClick={() => {
                  const i = SPEEDS.indexOf(speed)
                  setRate(SPEEDS[(i + 1) % SPEEDS.length])
                }}
                className="px-2 py-1 rounded text-2xs font-mono font-semibold text-fg-muted hover:text-copper-400 hover:bg-fg/5 transition tabular-nums"
                aria-label="Changer la vitesse de lecture"
                title="Vitesse de lecture"
              >
                {speed}×
              </button>
            </>
          )}
        </div>
      </div>

      {/* Indication raccourcis clavier — uniquement en non-compact */}
      {!compact && (
        <div className="mt-2 text-2xs text-fg-subtle flex items-center gap-2 opacity-0 group-focus-within:opacity-100 transition">
          <Volume2 size={10} />
          <span>Espace = lecture/pause · ← → = ±5s · clic sur la waveform pour naviguer</span>
        </div>
      )}

      <audio ref={audioRef} src={url} preload="metadata" />
    </div>
  )
}
