/**
 * Compat layer — l'ancien HUD a été remplacé par le thème Atelier.
 * On expose des wrappers vers PremiumCard pour préserver les imports
 * existants sans casser le build.
 */
import * as React from 'react'

import { PremiumCard } from './PremiumCard'
import { cn } from '@/utils/cn'

type Color = 'copper' | 'cyan' | 'green' | 'amber' | 'rose'

export function HudCard(props: React.HTMLAttributes<HTMLDivElement> & { padded?: boolean }) {
  return <PremiumCard variant="flat" {...props} />
}

export function HudLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('section-title', className)}>{children}</div>
}

const COLOR_TO_CHIP: Record<Color, string> = {
  copper: 'chip-copper',
  cyan:   'chip-info',
  green:  'chip-success',
  amber:  'chip-warning',
  rose:   'chip-danger',
}

export function HudBadge({
  children,
  color = 'copper',
}: { children: React.ReactNode; color?: Color }) {
  return <span className={COLOR_TO_CHIP[color] ?? 'chip-quiet'}>{children}</span>
}
