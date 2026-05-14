import { useEffect, useState } from 'react'

import { cn } from '@/utils/cn'

/**
 * NeonNumber — compteur animé (cubic-out).
 * Renommage conservé pour compat ; le composant n'a plus de glow néon
 * (thème Atelier). Le hint visuel est porté par la couleur passée en parent.
 */
export function NeonNumber({
  value, duration = 1200, className,
}: { value: number; duration?: number; color?: unknown; className?: string }) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const from = display
    const delta = value - from
    function step(t: number) {
      const p = Math.min(1, (t - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      setDisplay(Math.round(from + delta * eased))
      if (p < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])
  return <span className={cn('tabular', className)}>{display}</span>
}
