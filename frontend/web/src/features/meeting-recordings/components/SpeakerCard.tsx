// Card de voix détectée : durée, segments, extrait audio, select participant.
import { Mic, Volume2 } from 'lucide-react'

import { cn } from '@/utils/cn'

import { SmartAudioPlayer } from './SmartAudioPlayer'
import { SpeakerParticipantSelect } from './SpeakerParticipantSelect'
import type { DetectedSpeaker } from '../types/recording.types'

interface Participant {
  id: string
  full_name: string
  email: string
  role?: string
}

interface Props {
  speaker: DetectedSpeaker
  participants: Participant[]
  onChange: (speakerLabel: string, participantId: string | null) => void
  disabled?: boolean
}

function formatDuration(s: number): string {
  if (!s) return '0 sec'
  const sec = Math.round(s)
  if (sec < 60) return `${sec} sec`
  const m = Math.floor(sec / 60)
  const r = sec % 60
  return `${m} min ${String(r).padStart(2, '0')}`
}

export function SpeakerCard({ speaker, participants, onChange, disabled }: Props) {
  const mapped = speaker.mapped_participant?.id ?? null
  const suggested = speaker.suggested_participant?.id ?? null
  const sampleUrl = speaker.sample_audio_url

  return (
    <div className={cn(
      'p-4 rounded-xl border bg-bg-elevated transition',
      speaker.is_confirmed
        ? 'border-emerald-500/30 bg-emerald-500/5'
        : 'border-border',
    )}>
      <div className="flex items-start gap-3 mb-3">
        <div className="w-10 h-10 rounded-full bg-copper-500/10 text-copper-400 grid place-items-center shrink-0">
          <Mic size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tabular-nums">
              {speaker.speaker_label}
            </span>
            {speaker.is_confirmed && (
              <span className="text-2xs uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400">
                confirmé
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-fg-muted">
            <span>{formatDuration(speaker.total_duration)}</span>
            <span className="text-fg-subtle">·</span>
            <span>{speaker.total_segments} segment{speaker.total_segments > 1 ? 's' : ''}</span>
          </div>
        </div>
      </div>

      {sampleUrl ? (
        <SmartAudioPlayer url={sampleUrl} label="Extrait représentatif" compact className="mb-4" />
      ) : (
        <div className="mb-4 flex items-center gap-2 text-2xs text-fg-subtle">
          <Volume2 size={12} /> Extrait audio non disponible pour cette voix.
        </div>
      )}

      <div>
        <label className="text-2xs uppercase tracking-wider text-fg-subtle mb-1.5 block">
          Associer à un participant
        </label>
        <SpeakerParticipantSelect
          participants={participants}
          value={mapped}
          suggested={suggested}
          onChange={(pid) => onChange(speaker.speaker_label, pid)}
          disabled={disabled}
        />
      </div>
    </div>
  )
}
