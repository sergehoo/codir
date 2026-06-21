/**
 * useBrandingTheme — applique les couleurs de l'organisation courante en tant
 * que CSS variables sur :root.
 *
 * Tailwind du projet utilise `hsl(var(--copper-500))` pour la couleur de marque.
 * Override ces variables au runtime permet de changer toute l'application sans
 * recompiler ni toucher aux composants : boutons, chips, focus rings, shadows,
 * background gradients, scrollbar, selection, tout suit.
 *
 * Stratégie :
 *   1. Convertir la primary_color (hex) en HSL `H S% L%` (sans wrapper hsl()).
 *   2. Dériver la palette 50→900 en faisant varier uniquement la lightness (L)
 *      autour du pivot 500 — la teinte (H) et saturation (S) sont préservées
 *      pour cohérence visuelle.
 *   3. Set les 10 CSS variables sur :root via `style.setProperty`.
 *   4. Marquer `data-brand-custom="true"` pour permettre des overrides CSS
 *      conditionnels si besoin (ex. désactiver shadow-copper inset).
 *
 * Au logout / org sans branding custom, on REMOVE les overrides → fallback
 * automatique vers les valeurs Kaydan définies dans styles.css.
 */
import { useEffect } from 'react'

import { useCurrentMembership } from '@/stores/auth'

// Valeurs Kaydan par défaut (doivent rester synchro avec styles.css).
// Si la primary_color de l'org === KAYDAN_PIVOT_HEX, on saute l'override.
const KAYDAN_PIVOT_HEX = '#B8693C'

// Échelle des lightness pour chaque palier — calibrée pour donner une rampe
// agréable visuellement quel que soit le hue source (testé sur Kaydan #B8693C,
// Saphir #2563EB, Émeraude #10B981, Rubis #DC2626, Améthyste #7C3AED).
const LIGHTNESS_SCALE: Record<number, number> = {
  50:  94,
  100: 88,
  200: 78,
  300: 66,
  400: 56,
  500: 47,  // pivot
  600: 38,
  700: 30,
  800: 22,
  900: 15,
}

/**
 * Convertit #RRGGBB en {h, s, l} (h:0-360, s:0-100, l:0-100).
 * Supporte aussi #RGB (forme courte).
 */
function hexToHsl(hex: string): { h: number; s: number; l: number } | null {
  if (!hex) return null
  let s = hex.trim().replace('#', '')
  if (s.length === 3) s = s.split('').map((c) => c + c).join('')
  if (!/^[0-9a-fA-F]{6}$/.test(s)) return null

  const r = parseInt(s.substring(0, 2), 16) / 255
  const g = parseInt(s.substring(2, 4), 16) / 255
  const b = parseInt(s.substring(4, 6), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  let h = 0
  let sat = 0
  if (max !== min) {
    const d = max - min
    sat = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break
      case g: h = (b - r) / d + 2; break
      case b: h = (r - g) / d + 4; break
    }
    h *= 60
  }
  return {
    h: Math.round(h),
    s: Math.round(sat * 100),
    l: Math.round(l * 100),
  }
}

const COPPER_VARS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]

function applyBrandingToRoot(primaryHex: string | null, secondaryHex?: string | null) {
  if (typeof document === 'undefined') return  // SSR safety
  const root = document.documentElement

  // Pas de branding ou identique au Kaydan défaut → on nettoie tous les overrides
  // pour laisser styles.css reprendre la main.
  if (
    !primaryHex
    || primaryHex.toLowerCase() === KAYDAN_PIVOT_HEX.toLowerCase()
  ) {
    COPPER_VARS.forEach((n) => root.style.removeProperty(`--copper-${n}`))
    root.style.removeProperty('--brand-primary-hex')
    root.style.removeProperty('--brand-secondary-hex')
    root.removeAttribute('data-brand-custom')
    return
  }

  const hsl = hexToHsl(primaryHex)
  if (!hsl) {
    // Hex invalide — on nettoie (fallback Kaydan)
    COPPER_VARS.forEach((n) => root.style.removeProperty(`--copper-${n}`))
    root.removeAttribute('data-brand-custom')
    return
  }

  // Override chaque palier en gardant H et S, variant uniquement L.
  COPPER_VARS.forEach((n) => {
    const targetL = LIGHTNESS_SCALE[n]
    root.style.setProperty(`--copper-${n}`, `${hsl.h} ${hsl.s}% ${targetL}%`)
  })

  // Variables miroir pour usage direct sans Tailwind (ex. inline styles)
  root.style.setProperty('--brand-primary-hex', primaryHex)
  if (secondaryHex) root.style.setProperty('--brand-secondary-hex', secondaryHex)
  root.setAttribute('data-brand-custom', 'true')
}

/**
 * Hook : injecte la palette org dans :root chaque fois que le membership
 * courant change (notamment au switch d'organisation ou au login).
 *
 * Branche-le DANS LE SHELL au plus haut niveau de l'arbre authentifié pour
 * que la couleur soit appliquée avant tout rendu des pages.
 */
export function useBrandingTheme() {
  const membership = useCurrentMembership()
  const primary = membership?.primary_color || null
  const secondary = membership?.secondary_color || null

  useEffect(() => {
    applyBrandingToRoot(primary, secondary)
  }, [primary, secondary])

  // Cleanup au unmount (logout = Shell unmount)
  useEffect(() => {
    return () => applyBrandingToRoot(null, null)
  }, [])
}
