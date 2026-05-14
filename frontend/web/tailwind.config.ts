import type { Config } from 'tailwindcss'

/**
 * CODIR Executive Platform — Tailwind v3 (Atelier theme)
 *
 * Direction artistique « Atelier » :
 *   - Palette : ivoire / anthracite / cuivre / or
 *   - Typo display : Fraunces (serif éditorial) — corps : Inter Tight
 *   - Aucun glow néon, ombres douces multi-couches
 *   - Espacements généreux, esprit private banking digital
 *
 * Mode dark par défaut, light en option (toggle).
 */
export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    container: { center: true, padding: '1.5rem' },
    extend: {
      colors: {
        // ─── Brand cuivre / or (refined, pas néon) ──────────────
        copper: {
          50:  'hsl(var(--copper-50))',
          100: 'hsl(var(--copper-100))',
          200: 'hsl(var(--copper-200))',
          300: 'hsl(var(--copper-300))',
          400: 'hsl(var(--copper-400))',   // gilded / luxe
          500: 'hsl(var(--copper-500))',   // pivot brand
          600: 'hsl(var(--copper-600))',   // deeper
          700: 'hsl(var(--copper-700))',
          800: 'hsl(var(--copper-800))',
          900: 'hsl(var(--copper-900))',
        },
        gold: 'hsl(var(--gold))',          // accent luxe (rare)
        // ─── Surfaces ───────────────────────────────────────────
        bg: {
          base:     'hsl(var(--bg-base))',
          subtle:   'hsl(var(--bg-subtle))',
          elevated: 'hsl(var(--bg-elevated))',
          inverted: 'hsl(var(--bg-inverted))',
        },
        fg: {
          DEFAULT:  'hsl(var(--fg))',
          muted:    'hsl(var(--fg-muted))',
          subtle:   'hsl(var(--fg-subtle))',
          inverted: 'hsl(var(--fg-inverted))',
        },
        border: {
          DEFAULT: 'hsl(var(--border))',
          strong:  'hsl(var(--border-strong))',
          accent:  'hsl(var(--border-accent))',
        },
        // ─── Sémantique (tons feutrés, pas saturés) ─────────────
        success: { DEFAULT: 'hsl(var(--success))', soft: 'hsl(var(--success-soft))' },
        warning: { DEFAULT: 'hsl(var(--warning))', soft: 'hsl(var(--warning-soft))' },
        danger:  { DEFAULT: 'hsl(var(--danger))',  soft: 'hsl(var(--danger-soft))'  },
        info:    { DEFAULT: 'hsl(var(--info))',    soft: 'hsl(var(--info-soft))'    },
      },
      fontFamily: {
        // Editorial display headlines
        display: ['Fraunces', 'Tiempos Headline', 'Georgia', 'serif'],
        // Body & UI sans
        sans: ['Inter Tight', 'Inter', 'system-ui', 'sans-serif'],
        // Tabular pour KPI / refs
        mono: ['JetBrains Mono', 'IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs':      ['0.6875rem', { lineHeight: '1rem',  letterSpacing: '0.04em' }],
        // Display (serif, généreux)
        'hero':     ['4.5rem',    { lineHeight: '1.02', letterSpacing: '-0.035em', fontWeight: '500' }],
        'display':  ['3rem',      { lineHeight: '1.05', letterSpacing: '-0.025em', fontWeight: '500' }],
        'editorial':['2.25rem',   { lineHeight: '1.1',  letterSpacing: '-0.02em',  fontWeight: '500' }],
        // KPI numerics (tabular, serif option)
        'kpi-xl':   ['3.5rem',    { lineHeight: '1',    letterSpacing: '-0.03em',  fontWeight: '500' }],
        'kpi':      ['2.5rem',    { lineHeight: '1',    letterSpacing: '-0.025em', fontWeight: '500' }],
        'kpi-sm':   ['1.75rem',   { lineHeight: '1',    letterSpacing: '-0.02em',  fontWeight: '500' }],
        // Sans hierarchy
        'h1':       ['1.625rem',  { lineHeight: '1.2',  letterSpacing: '-0.015em', fontWeight: '600' }],
        'h2':       ['1.25rem',   { lineHeight: '1.3',                            fontWeight: '600' }],
        'h3':       ['1.0625rem', { lineHeight: '1.4',                            fontWeight: '600' }],
      },
      letterSpacing: { wide: '0.04em', wider: '0.08em', widest: '0.18em' },
      borderRadius: {
        DEFAULT: '0.5rem',
        xs: '0.25rem',
        sm: '0.375rem',
        md: '0.5rem',
        lg: '0.625rem',
        xl: '0.75rem',
        '2xl': '1rem',
        '3xl': '1.25rem',
      },
      spacing: {
        '4.5': '1.125rem', '5.5': '1.375rem', '7.5': '1.875rem',
        '13': '3.25rem', '15': '3.75rem', '18': '4.5rem',
        '22': '5.5rem', '26': '6.5rem',
      },
      boxShadow: {
        // Soft layered shadows (Atelier signature)
        whisper: '0 1px 2px rgba(20,16,12,0.04)',
        soft:    '0 2px 4px rgba(20,16,12,0.04), 0 4px 12px rgba(20,16,12,0.05)',
        card:    '0 4px 8px -2px rgba(20,16,12,0.06), 0 12px 24px -8px rgba(20,16,12,0.07)',
        raised:  '0 8px 20px -8px rgba(20,16,12,0.12), 0 16px 32px -12px rgba(20,16,12,0.08)',
        floating:'0 20px 40px -16px rgba(20,16,12,0.20), 0 32px 64px -24px rgba(20,16,12,0.12)',
        // Brand subtle (jamais glow)
        copper:  '0 1px 0 hsl(var(--copper-500) / 0.4) inset, 0 8px 16px -6px hsl(var(--copper-500) / 0.18)',
        inset:   'inset 0 0 0 1px hsl(var(--border) / 0.6)',
      },
      transitionTimingFunction: {
        editorial: 'cubic-bezier(0.32, 0.72, 0.32, 1)',
        spring:    'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      transitionDuration: { '250': '250ms', '350': '350ms', '450': '450ms', '600': '600ms' },
      keyframes: {
        'fade-in':       { from: { opacity: '0' },                              to: { opacity: '1' } },
        'fade-in-up':    { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'rise':          { from: { opacity: '0', transform: 'translateY(16px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'soft-pulse':    { '0%, 100%': { opacity: '1' },                         '50%': { opacity: '0.55' } },
        'ink-slide':     { from: { transform: 'scaleX(0)', transformOrigin: 'left' }, to: { transform: 'scaleX(1)', transformOrigin: 'left' } },
      },
      animation: {
        'fade-in':    'fade-in 280ms cubic-bezier(0.32,0.72,0.32,1) both',
        'fade-in-up': 'fade-in-up 350ms cubic-bezier(0.32,0.72,0.32,1) both',
        'rise':       'rise 520ms cubic-bezier(0.32,0.72,0.32,1) both',
        'soft-pulse': 'soft-pulse 2.4s ease-in-out infinite',
        'ink-slide':  'ink-slide 600ms cubic-bezier(0.32,0.72,0.32,1) both',
      },
      backgroundImage: {
        'copper-gradient': 'linear-gradient(135deg, hsl(var(--copper-600)) 0%, hsl(var(--copper-500)) 50%, hsl(var(--copper-400)) 100%)',
        'editorial-mesh':  `radial-gradient(at 20% 18%, hsl(var(--copper-500) / 0.06), transparent 55%),
                            radial-gradient(at 82% 75%, hsl(var(--gold) / 0.05), transparent 55%),
                            linear-gradient(180deg, hsl(var(--bg-base)) 0%, hsl(var(--bg-subtle)) 100%)`,
      },
    },
  },
  plugins: [],
} satisfies Config
