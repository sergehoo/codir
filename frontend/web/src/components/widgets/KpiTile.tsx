import * as React from 'react'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'

import { cn } from '@/utils/cn'
import { NeonNumber } from './NeonNumber'
import { PremiumCard } from './PremiumCard'

type Trend = 'up' | 'down' | 'flat'

const TREND_ICON: Record<Trend, React.ComponentType<{ size?: number }>> = {
  up: ArrowUpRight,
  down: ArrowDownRight,
  flat: Minus,
}

const TREND_COLOR: Record<Trend, string> = {
  up: 'text-success',
  down: 'text-danger',
  flat: 'text-fg-muted',
}

/**
 * KpiTile (Atelier) — tuile KPI éditoriale.
 *
 *   - chiffre en Fraunces (serif) tabular pour autorité
 *   - label en small caps cuivre
 *   - tendance en chip discret
 */
export function KpiTile({
  label, value, suffix, deltaLabel, trend = 'flat',
  sparkline, hint, serif = true,
}: {
  label: string
  value: number
  suffix?: string
  deltaLabel?: string
  trend?: Trend
  sparkline?: React.ReactNode
  hint?: string
  serif?: boolean
}) {
  const TrendIcon = TREND_ICON[trend]
  return (
    <PremiumCard variant="flat">
      <div className="flex items-baseline justify-between mb-3">
        <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
          {label}
        </span>
        {deltaLabel && (
          <span className={cn('inline-flex items-center gap-0.5 text-2xs font-medium', TREND_COLOR[trend])}>
            <TrendIcon size={12} /> {deltaLabel}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2">
        <span className={cn('kpi text-kpi text-fg', serif && 'serif')}>
          <NeonNumber value={value} color="cyan" className="" />
        </span>
        {suffix && <span className="text-fg-muted text-sm font-medium">{suffix}</span>}
      </div>
      {sparkline && <div className="mt-3">{sparkline}</div>}
      {hint && <div className="text-2xs text-fg-subtle mt-3 tracking-wider uppercase">{hint}</div>}
    </PremiumCard>
  )
}
