// Select : associe une voix (SPEAKER_XX) à un participant de la réunion.
import { Check, ChevronDown, User } from 'lucide-react'
import { useState } from 'react'

import { cn } from '@/utils/cn'

interface Participant {
  id: string
  full_name: string
  email: string
  role?: string
}

interface Props {
  participants: Participant[]
  value: string | null
  suggested?: string | null
  onChange: (participantId: string | null) => void
  disabled?: boolean
}

export function SpeakerParticipantSelect({
  participants, value, suggested, onChange, disabled,
}: Props) {
  const [open, setOpen] = useState(false)
  const selected = participants.find((p) => p.id === value) ?? null

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg border text-sm transition',
          disabled && 'opacity-60 cursor-not-allowed',
          selected
            ? 'border-copper-500/40 bg-copper-500/5 text-fg'
            : 'border-border bg-bg-base hover:bg-fg/5 text-fg-muted',
        )}
      >
        <span className="flex items-center gap-2 truncate">
          <User size={14} className="shrink-0" />
          <span className="truncate">
            {selected ? selected.full_name : 'Sélectionner un participant…'}
          </span>
        </span>
        <ChevronDown size={14} className={cn('transition-transform', open && 'rotate-180')} />
      </button>

      {open && !disabled && (
        <div
          className="absolute z-30 left-0 right-0 mt-1 max-h-64 overflow-y-auto rounded-lg border border-border bg-bg-elevated shadow-xl"
          role="listbox"
        >
          <button
            type="button"
            onClick={() => { onChange(null); setOpen(false) }}
            className="w-full text-left px-3 py-2 text-xs text-fg-muted hover:bg-fg/5 border-b border-border"
          >
            — Désassocier —
          </button>
          {participants.map((p) => {
            const isSelected = p.id === value
            const isSuggested = p.id === suggested
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => { onChange(p.id); setOpen(false) }}
                className={cn(
                  'w-full flex items-center justify-between gap-2 px-3 py-2 text-sm hover:bg-fg/5 transition',
                  isSelected && 'bg-copper-500/10 text-copper-400',
                )}
              >
                <span className="flex flex-col items-start min-w-0">
                  <span className="truncate w-full">{p.full_name}</span>
                  <span className="text-2xs text-fg-subtle truncate w-full">{p.email}</span>
                </span>
                {isSelected ? (
                  <Check size={14} className="text-copper-400 shrink-0" />
                ) : isSuggested ? (
                  <span className="text-2xs uppercase tracking-wider text-copper-400">
                    suggéré
                  </span>
                ) : null}
              </button>
            )
          })}
          {participants.length === 0 && (
            <div className="px-3 py-3 text-xs text-fg-subtle text-center">
              Aucun participant disponible.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
