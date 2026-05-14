import { NeonNumber } from './NeonNumber'

/**
 * AtelierGauge — jauge SVG sobre éditoriale.
 *
 * Pas d'anneau pointillé rotatif, pas de glow.
 * Juste un arc cuivre épais + valeur centrale en serif.
 */
export function AtelierGauge({
  value, max = 100, label, hint, size = 160,
}: {
  value: number
  max?: number
  label?: string
  hint?: string
  size?: number
}) {
  const radius = 70
  const circumference = 2 * Math.PI * radius
  const ratio = Math.min(1, Math.max(0, value / max))
  const offset = circumference * (1 - ratio)
  return (
    <div className="text-center">
      {label && (
        <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-3">{label}</div>
      )}
      <div className="relative inline-block">
        <svg viewBox="0 0 160 160" style={{ width: size, height: size }}>
          {/* Track */}
          <circle cx="80" cy="80" r={radius}
                  fill="none" stroke="hsl(var(--border))" strokeWidth="3" />
          {/* Progress arc cuivre */}
          <circle cx="80" cy="80" r={radius}
                  fill="none" stroke="hsl(var(--copper-500))" strokeWidth="3.5"
                  strokeDasharray={circumference}
                  strokeDashoffset={offset}
                  strokeLinecap="round"
                  transform="rotate(-90 80 80)"
                  style={{ transition: 'stroke-dashoffset 1.4s cubic-bezier(0.32,0.72,0.32,1)' }} />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <div className="kpi-serif text-kpi-sm">
            <NeonNumber value={value} duration={1400} />
          </div>
        </div>
      </div>
      {hint && (
        <div className="text-2xs text-fg-subtle mt-3 tracking-wider uppercase">{hint}</div>
      )}
    </div>
  )
}
