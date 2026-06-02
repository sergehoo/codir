// Lecteur audio inline pour les extraits speakers (sample_audio_url).
import { Pause, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { cn } from '@/utils/cn'

interface Props {
  url: string
  label?: string
  className?: string
}

export function SpeakerSamplePlayer({ url, label, className }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    const a = audioRef.current
    if (!a) return
    const onTime = () => setCurrentTime(a.currentTime)
    const onMeta = () => setDuration(a.duration || 0)
    const onEnd = () => { setPlaying(false); setCurrentTime(0) }
    a.addEventListener('timeupdate', onTime)
    a.addEventListener('loadedmetadata', onMeta)
    a.addEventListener('ended', onEnd)
    return () => {
      a.removeEventListener('timeupdate', onTime)
      a.removeEventListener('loadedmetadata', onMeta)
      a.removeEventListener('ended', onEnd)
    }
  }, [])

  const toggle = () => {
    const a = audioRef.current
    if (!a) return
    if (playing) {
      a.pause(); setPlaying(false)
    } else {
      a.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
    }
  }

  const pct = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <button
        type="button"
        onClick={toggle}
        className={cn(
          'w-9 h-9 rounded-full grid place-items-center transition',
          playing
            ? 'bg-copper-500 text-white hover:bg-copper-600'
            : 'bg-fg/10 text-fg hover:bg-fg/20',
        )}
        aria-label={playing ? 'Pause' : 'Écouter'}
      >
        {playing ? <Pause size={14} /> : <Play size={14} fill="currentColor" />}
      </button>
      <div className="flex-1 min-w-0 space-y-1">
        {label && (
          <div className="text-2xs uppercase tracking-wider text-fg-subtle">{label}</div>
        )}
        <div className="h-1.5 w-full rounded-full bg-fg/10 overflow-hidden">
          <div
            className="h-full bg-copper-500 transition-[width] duration-150"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <span className="text-2xs font-mono tabular-nums text-fg-subtle min-w-[44px] text-right">
        {format(currentTime)} / {format(duration)}
      </span>
      <audio ref={audioRef} src={url} preload="metadata" />
    </div>
  )
}

function format(s: number): string {
  if (!s || !isFinite(s)) return '0:00'
  const sec = Math.floor(s)
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
}
