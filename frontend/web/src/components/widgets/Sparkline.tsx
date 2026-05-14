/**
 * Sparkline minimaliste — SVG pur, sans dépendance externe.
 * Pour des charts plus complexes utiliser Recharts.
 */
export function Sparkline({
  data,
  color = 'hsl(var(--copper-500))',
  height = 28,
  width = 100,
}: {
  data: number[]
  color?: string
  height?: number
  width?: number
}) {
  if (data.length < 2) {
    return <div className="text-2xs text-fg-subtle">—</div>
  }
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const step = width / (data.length - 1)
  const points = data
    .map((v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / range) * height).toFixed(1)}`)
    .join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="overflow-visible" width={width} height={height}>
      {/* Area sous la courbe */}
      <polyline
        points={`0,${height} ${points} ${width},${height}`}
        fill={color} fillOpacity="0.12"
      />
      {/* Ligne */}
      <polyline
        points={points} fill="none"
        stroke={color} strokeWidth="1.5"
        strokeLinejoin="round" strokeLinecap="round"
      />
      {/* Dernier point */}
      <circle
        cx={width} cy={height - ((data[data.length - 1] - min) / range) * height}
        r="2.5" fill={color}
      />
    </svg>
  )
}
