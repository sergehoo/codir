import * as React from 'react'
import { cn } from '@/utils/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'link'
type Size = 'sm' | 'md' | 'lg'

const VARIANTS: Record<Variant, string> = {
  primary:   'bg-copper-500 text-white shadow-copper hover:bg-copper-600 active:scale-[0.99]',
  secondary: 'bg-bg-elevated text-fg border border-border hover:border-copper-500/40 hover:bg-bg-subtle',
  ghost:     'text-fg-muted hover:text-fg hover:bg-fg/[0.04]',
  danger:    'bg-danger text-white hover:bg-danger/90',
  link:      'text-copper-400 hover:text-copper-500 underline underline-offset-4 decoration-copper-500/40 hover:decoration-copper-500 px-0 py-0',
}

const SIZES: Record<Size, string> = {
  sm: 'px-3.5 py-1.5 text-xs gap-1.5',
  md: 'px-5 py-2.5 text-sm gap-2',
  lg: 'px-6 py-3 text-base gap-2.5',
}

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
  iconLeft?: React.ReactNode
  iconRight?: React.ReactNode
  loading?: boolean
}

export const PremiumButton = React.forwardRef<HTMLButtonElement, Props>(
  ({ variant = 'primary', size = 'md', iconLeft, iconRight, loading, className, children, disabled, ...rest }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium whitespace-nowrap',
        'transition-all duration-250 ease-editorial',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-copper-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        VARIANTS[variant],
        variant !== 'link' && SIZES[size],
        className,
      )}
      {...rest}
    >
      {loading ? (
        <span className="inline-block w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
      ) : iconLeft}
      {children}
      {!loading && iconRight}
    </button>
  ),
)
PremiumButton.displayName = 'PremiumButton'
