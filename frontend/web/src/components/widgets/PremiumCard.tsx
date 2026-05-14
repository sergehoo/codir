import * as React from 'react'
import { cn } from '@/utils/cn'

type Variant = 'flat' | 'elevated' | 'paper'

type Props = React.HTMLAttributes<HTMLDivElement> & {
  variant?: Variant
  padded?: boolean
}

/**
 * PremiumCard — Atelier theme. Esthétique papier/journal feutré.
 *
 *   - flat       : surface bg-elevated avec border
 *   - elevated   : ombre légère (hover plus marquée)
 *   - paper      : sans ombre, juste border-bottom cuivre (style editorial)
 */
export function PremiumCard({
  variant = 'flat',
  padded = true,
  className,
  children,
  ...rest
}: Props) {
  const base =
    variant === 'elevated' ? 'card-elevated'
    : variant === 'paper'  ? 'card-quiet border-l-2 border-copper-500/40 border-t-0 border-r-0 border-b-0 rounded-r-xl rounded-l-none'
    : 'card'
  return (
    <div className={cn(base, padded && 'p-6', className)} {...rest}>
      {children}
    </div>
  )
}

export function CardLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('section-title', className)}>{children}</div>
  )
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h3 className={cn('text-h2 font-semibold', className)}>{children}</h3>
}
