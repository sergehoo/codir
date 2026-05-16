import { cn } from '@/utils/cn'

type Props = {
  /**
   * - `full`     : logo officiel Kaydan Groupe (PNG transparent haute qualité)
   * - `mark`     : carré 1:1 (K orange + bracket) — favicon-ready, SVG
   * - `wordmark` : ligne texte inline "Kaydan Groupe"
   */
  variant?: 'full' | 'mark' | 'wordmark'
  className?: string
  label?: string
  /**
   * @deprecated Le logo est désormais toujours transparent.
   * Cette prop est conservée pour compatibilité mais n'a plus d'effet.
   */
  filled?: boolean
}

const ORANGE = '#F97316'
const LOGO_PNG = '/logo_kaydanG_B.png'

/**
 * Logo officiel Kaydan Groupe — toujours fond transparent.
 *
 *   - `full`     : utilise le PNG officiel `/public/logo_kaydanG_B.png` (RGBA transparent)
 *   - `mark`     : SVG K + bracket (compact, favicon-ready)
 *   - `wordmark` : pur texte stylé "Kaydan Groupe"
 */
export function KaydanLogo({ variant = 'full', className, label }: Props) {

  if (variant === 'mark') {
    return (
      <svg viewBox="0 0 64 64" className={cn('h-9 w-9', className)} aria-label="Kaydan">
        <path d="M 36 10 L 54 10 L 54 28"
              stroke={ORANGE} strokeWidth="4" fill="none" strokeLinecap="square" />
        <text
          x="32" y="48" textAnchor="middle"
          fontSize="34" fontWeight="900"
          fontFamily="system-ui, -apple-system, Arial, sans-serif"
          fill="currentColor"
        >K</text>
      </svg>
    )
  }

  if (variant === 'wordmark') {
    return (
      <span className={cn('inline-flex items-baseline gap-2.5', className)}>
        {label && (
          <span className="text-2xs uppercase tracking-widest text-fg-subtle">{label}</span>
        )}
        <span className="inline-flex items-baseline gap-1.5">
          <span className="font-sans font-extrabold tracking-tight text-fg uppercase text-sm">
            Kaydan
          </span>
          <span className="text-2xs uppercase tracking-[0.22em] text-[#F97316] font-bold">
            Groupe
          </span>
        </span>
      </span>
    )
  }

  // full — PNG officiel transparent
  return (
    <span className={cn('inline-flex items-center', className)}>
      <img
        src={LOGO_PNG}
        alt="Kaydan Groupe"
        className="h-full w-auto object-contain max-h-full"
        draggable={false}
      />
    </span>
  )
}
