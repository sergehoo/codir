import { cn } from '@/utils/cn'

type Props = {
  variant?: 'full' | 'mark' | 'wordmark'
  className?: string
  label?: string
  /** Force le fond noir signature Kaydan (sinon transparent — s'adapte au thème). */
  filled?: boolean
}

const ORANGE = '#F97316'

/**
 * Logo officiel Kaydan Groupe.
 *
 *   - `full`     : banner "KAYDAN" + bracket + "GROUPE" (viewBox 420×175, ratio 2.4:1)
 *   - `mark`     : carré 1:1 (K + bracket) — favicon-ready
 *   - `wordmark` : ligne texte inline "Kaydan"
 */
export function KaydanLogo({ variant = 'full', className, label, filled = false }: Props) {

  if (variant === 'mark') {
    return (
      <svg viewBox="0 0 64 64" className={cn('h-9 w-9', className)} aria-label="Kaydan">
        {filled && <rect width="64" height="64" rx="10" fill="#0A0A0A" />}
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

  // full — banner officiel, viewBox serré au contenu
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 420 175"
      fill="none"
      className={cn(className)}
      aria-label="Kaydan Groupe"
    >
      {filled && <rect width="420" height="175" fill="#0A0A0A" />}

      <path
        d="M 280 10 L 410 10 L 410 80"
        stroke="#F97316"
        strokeWidth="14"
        strokeLinecap="square"
        fill="none"
      />

      <text
        x="20" y="115"
        fontFamily="Arial, Helvetica, sans-serif"
        fontSize="86"
        fontWeight="900"
        fill="#FFFFFF"
        letterSpacing="-2"
      >KAYDAN</text>

      <text
        x="260" y="160"
        fontFamily="Arial, Helvetica, sans-serif"
        fontSize="20"
        fontWeight="700"
        fill="#F97316"
        letterSpacing="3.5"
      >GROUPE</text>
    </svg>
  )
}
