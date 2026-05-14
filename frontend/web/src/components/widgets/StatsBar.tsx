import * as React from 'react'

import { cn } from '@/utils/cn'

type Tone = 'neutral' | 'copper' | 'success' | 'warning' | 'danger' | 'info'

const TONE_TEXT: Record<Tone, string> = {
  neutral: 'text-fg',
  copper:  'text-copper-400',
  success: 'text-success',
  warning: 'text-warning',
  danger:  'text-danger',
  info:    'text-info',
}

type StatItem = {
  label: string
  value: number | string
  tone?: Tone
  hint?: string
}

/**
 * Barre de stats horizontale éditoriale.
 *   Chiffre en serif tabular + label small caps en dessous.
 */
export function StatsBar({ items, className }: { items: StatItem[]; className?: string }) {
  return (
    <div className={cn(
      'card px-6 py-5 flex items-stretch gap-2 overflow-x-auto',
      className,
    )}>
      {items.map((it, i) => (
        <React.Fragment key={it.label}>
          {i > 0 && <div className="w-px bg-border mx-2 my-1" />}
          <div className="flex-1 min-w-[120px] px-3">
            <div className={cn(
              'serif text-kpi leading-none tabular',
              TONE_TEXT[it.tone ?? 'neutral'],
            )}>
              {it.value}
            </div>
            <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mt-2.5">
              {it.label}
            </div>
            {it.hint && (
              <div className="text-2xs text-fg-subtle mt-1 lowercase">{it.hint}</div>
            )}
          </div>
        </React.Fragment>
      ))}
    </div>
  )
}
