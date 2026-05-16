import { useState } from 'react'

import { NeonNumber } from './NeonNumber'

/**
 * MasterGauge — version Atelier : sobre, élégant, sans rotation.
 *
 * Un arc cuivre majestueux + valeur centrale en serif Fraunces,
 * sparkline 90j discrète sous le score, et popup explicatif avec
 * les 4 sous-scores (composantes EPI v2).
 */
export interface EpiBreakdown {
  overall_score: number
  completion_score: number
  punctuality_score: number
  velocity_score: number
  quorum_score: number
  overdue_penalty: number
  tasks_total: number
  tasks_done: number
  tasks_done_on_time: number
  tasks_overdue: number
  avg_days_to_close: number
  meetings_total: number
  meetings_quorum_reached: number
  weights: { completion: number; punctuality: number; velocity: number; quorum: number }
  windows: { tasks_days: number; velocity_days: number; meetings_days: number }
}

export function MasterGauge({
  value,
  label = 'EPI Score',
  trend = '',
  breakdown,
  sparkline = [],
}: {
  value: number
  label?: string
  trend?: string
  breakdown?: EpiBreakdown
  sparkline?: number[]
}) {
  const [showDetails, setShowDetails] = useState(false)
  const radius = 110
  const circumference = 2 * Math.PI * radius
  const ratio = Math.min(1, Math.max(0, value / 100))
  const offset = circumference * (1 - ratio)

  // Sparkline path : normalise sur 60..100 visible
  const spark = sparkline.length > 1
    ? (() => {
        const min = Math.min(...sparkline)
        const max = Math.max(...sparkline)
        const range = Math.max(max - min, 1)
        const w = 200
        const h = 28
        const pts = sparkline.map((v, i) => {
          const x = (i / (sparkline.length - 1)) * w
          const y = h - ((v - min) / range) * h
          return `${x.toFixed(1)},${y.toFixed(1)}`
        })
        return `M ${pts.join(' L ')}`
      })()
    : null

  return (
    <div className="relative w-full max-w-md mx-auto">
      <div className="relative aspect-square">
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

      {/* ─── Sparkline 90 jours ───────────────────────────────── */}
      {spark && (
        <div className="mt-3 px-4">
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-1 text-center">
            Évolution {sparkline.length} jours
          </div>
          <svg viewBox="0 0 200 28" className="w-full h-7">
            <path
              d={spark}
              fill="none"
              stroke="hsl(var(--copper-500))"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}

      {/* ─── Toggle breakdown ─────────────────────────────────── */}
      {breakdown && (
        <button
          type="button"
          onClick={() => setShowDetails((v) => !v)}
          className="mt-3 mx-auto block text-2xs uppercase tracking-widest text-fg-muted hover:text-copper-500 font-semibold transition"
        >
          {showDetails ? '— masquer les composantes' : '+ voir les composantes'}
        </button>
      )}

      {/* ─── Breakdown panel ──────────────────────────────────── */}
      {breakdown && showDetails && (
        <div className="mt-4 mx-2 rounded-lg border border-border bg-bg-elevated p-4 space-y-3 text-sm">
          <ScoreBar
            label="Complétion"
            value={breakdown.completion_score}
            weight={breakdown.weights.completion}
            hint={`${breakdown.tasks_done}/${breakdown.tasks_total} tâches dues sur ${breakdown.windows.tasks_days}j`}
          />
          <ScoreBar
            label="Ponctualité"
            value={breakdown.punctuality_score}
            weight={breakdown.weights.punctuality}
            hint={`${breakdown.tasks_done_on_time} tâches dans les délais`}
          />
          <ScoreBar
            label="Vélocité"
            value={breakdown.velocity_score}
            weight={breakdown.weights.velocity}
            hint={`${breakdown.avg_days_to_close.toFixed(1)} j moyen décision → fermeture`}
          />
          <ScoreBar
            label="Quorum CODIR"
            value={breakdown.quorum_score}
            weight={breakdown.weights.quorum}
            hint={`${breakdown.meetings_quorum_reached}/${breakdown.meetings_total} sur ${breakdown.windows.meetings_days}j`}
          />
          {breakdown.overdue_penalty > 0 && (
            <div className="flex items-center justify-between pt-2 border-t border-border text-danger">
              <span className="text-2xs uppercase tracking-widest font-semibold">
                Pénalité — {breakdown.tasks_overdue} tâche{breakdown.tasks_overdue > 1 ? 's' : ''} en retard
              </span>
              <span className="font-bold tabular-nums">−{breakdown.overdue_penalty} pts</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ScoreBar({
  label, value, weight, hint,
}: { label: string; value: number; weight: number; hint?: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
          {label} <span className="opacity-50">({weight}%)</span>
        </span>
        <span className="tabular-nums font-semibold text-fg">{value}/100</span>
      </div>
      <div className="h-1.5 bg-bg-base rounded-full overflow-hidden">
        <div
          className="h-full bg-copper-500 rounded-full transition-all duration-700"
          style={{ width: `${Math.max(2, value)}%` }}
        />
      </div>
      {hint && <div className="text-2xs text-fg-muted mt-1">{hint}</div>}
    </div>
  )
}
