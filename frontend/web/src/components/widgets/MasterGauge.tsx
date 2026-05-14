import { NeonNumber } from './NeonNumber'

/**
 * MasterGauge — version Atelier : sobre, élégant, sans rotation.
 *
 * Un arc cuivre majestueux + valeur centrale en serif Fraunces.
 */
export function MasterGauge({
  value, label = 'EPI Score', trend = '',
}: { value: number; label?: string; trend?: string }) {
  const radius = 110
  const circumference = 2 * Math.PI * radius
  const ratio = Math.min(1, Math.max(0, value / 100))
  const offset = circumference * (1 - ratio)
  return (
    <div className="relative aspect-square w-full max-w-md mx-auto">
      <svg viewBox="0 0 280 280" className="w-full h-full">
        {/* Anneau de fond très discret */}
        <circle cx="140" cy="140" r={radius}
                fill="none" stroke="hsl(var(--border))" strokeWidth="6" />

        {/* Arc cuivre */}
        <circle cx="140" cy="140" r={radius}
                fill="none" stroke="url(#copperGrad)" strokeWidth="6.5"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                strokeLinecap="round"
                transform="rotate(-90 140 140)"
                style={{ transition: 'stroke-dashoffset 1.8s cubic-bezier(0.32,0.72,0.32,1)' }} />

        <defs>
          <linearGradient id="copperGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%"  stopColor="hsl(var(--copper-600))" />
            <stop offset="60%" stopColor="hsl(var(--copper-500))" />
            <stop offset="100%" stopColor="hsl(var(--copper-400))" />
          </linearGradient>
        </defs>

        {/* Petits ticks discrets aux 4 cardinaux */}
        {[0, 90, 180, 270].map((angle) => (
          <line
            key={angle}
            x1="140" y1="22" x2="140" y2="32"
            stroke="hsl(var(--copper-500) / 0.5)" strokeWidth="1"
            transform={`rotate(${angle} 140 140)`}
          />
        ))}
      </svg>

      <div className="absolute inset-0 grid place-items-center pointer-events-none">
        <div className="text-center">
          <NeonNumber value={value} duration={1800} className="serif text-hero text-fg" />
          <div className="text-2xs tracking-widest text-fg-muted mt-2 uppercase font-semibold">
            {label}
          </div>
          {trend && (
            <div className="text-2xs text-success mt-1 font-medium">{trend}</div>
          )}
        </div>
      </div>
    </div>
  )
}
