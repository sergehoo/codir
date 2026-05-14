/**
 * Spectrum (Atelier) — version sobre éditoriale.
 *
 * Remplace l'ancienne barre audio-réactive HUD par un histogramme
 * subtil en cuivre (statique, hauteurs déterministes).
 */
const HEIGHTS = [0.35, 0.62, 0.45, 0.78, 0.55, 0.92, 0.48, 0.7, 0.4, 0.85, 0.6, 0.52, 0.75, 0.42, 0.65, 0.88, 0.5, 0.72, 0.45, 0.6, 0.38, 0.58]

export function Spectrum({ bars = 22, height = 96 }: { bars?: number; height?: number }) {
  return (
    <div className="flex items-end gap-[3px]" style={{ height }}>
      {Array.from({ length: bars }).map((_, i) => {
        const h = HEIGHTS[i % HEIGHTS.length]
        return (
          <div
            key={i}
            className="flex-1 rounded-sm bg-gradient-to-t from-copper-500/15 to-copper-500/70 transition-all duration-300"
            style={{ height: `${h * 100}%` }}
          />
        )
      })}
    </div>
  )
}
