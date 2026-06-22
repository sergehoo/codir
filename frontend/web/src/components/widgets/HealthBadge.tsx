/**
 * HealthBadge — pastille discrète indiquant la santé d'un objet (plan, décision).
 *
 * Conçue pour s'insérer dans les listes de cartes sans dominer le visuel.
 * Tooltip détaillé au survol (reasons).
 *
 * Variants :
 *  - dot     : pastille colorée seule (8px) — pour les cartes denses
 *  - chip    : pastille + score + label (compact) — pour les listes normales
 *  - full    : pastille + label + 1ère raison — pour les détails
 */
import { cn } from '@/utils/cn'

export type HealthLabel = 'healthy' | 'watch' | 'at_risk' | 'critical'

const TONE: Record<HealthLabel, { dot: string; ring: string; text: string; bg: string }> = {
  healthy:  { dot: 'bg-success',  ring: 'ring-success/30',  text: 'text-success',  bg: 'bg-success/10' },
  watch:    { dot: 'bg-warning',  ring: 'ring-warning/30',  text: 'text-warning',  bg: 'bg-warning/10' },
  at_risk:  { dot: 'bg-copper-500',ring:'ring-copper-500/30',text:'text-copper-400',bg:'bg-copper-500/10' },
  critical: { dot: 'bg-danger',   ring: 'ring-danger/40',   text: 'text-danger',   bg: 'bg-danger/10' },
}

const FR: Record<HealthLabel, string> = {
  healthy:  'sain',
  watch:    'à surveiller',
  at_risk:  'à risque',
  critical: 'critique',
}

interface Props {
  score?: number
  label?: HealthLabel
  reasons?: string[]
  variant?: 'dot' | 'chip' | 'full'
  className?: string
}

export function HealthBadge({
  score, label, reasons = [], variant = 'chip', className,
}: Props) {
  if (label === undefined || score === undefined) return null
  const t = TONE[label]
  const tooltip = [
    `Santé : ${FR[label]} (${score}/100)`,
    ...reasons.slice(0, 3).map((r) => `• ${r}`),
  ].join('\n')

  if (variant === 'dot') {
    return (
      <span
        title={tooltip}
        className={cn('inline-block w-2 h-2 rounded-full ring-2', t.dot, t.ring, className)}
        aria-label={`Santé : ${FR[label]}`}
      />
    )
  }

  if (variant === 'chip') {
    return (
      <span
        title={tooltip}
        className={cn(
          'inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded text-2xs uppercase tracking-wider font-semibold',
          t.bg, t.text, className,
        )}
      >
        <span className={cn('w-1.5 h-1.5 rounded-full', t.dot)} />
        {score}
      </span>
    )
  }

  // full
  return (
    <div
      title={tooltip}
      className={cn(
        'inline-flex items-center gap-2 px-2 py-1 rounded',
        t.bg, t.text, className,
      )}
    >
      <span className={cn('w-2 h-2 rounded-full', t.dot)} />
      <span className="text-2xs uppercase tracking-wider font-semibold">
        {FR[label]} · {score}
      </span>
      {reasons.length > 0 && (
        <span className="text-2xs text-fg-muted truncate max-w-[200px]">
          {reasons[0]}
        </span>
      )}
    </div>
  )
}
