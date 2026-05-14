import * as React from 'react'
import { X } from 'lucide-react'

import { cn } from '@/utils/cn'

type Props = {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg'
}

const SIZE_CLASS: Record<NonNullable<Props['size']>, string> = {
  sm: 'max-w-md',
  md: 'max-w-xl',
  lg: 'max-w-3xl',
}

/** Modal sobre éditorial avec overlay flouté, animation rise et close button discret. */
export function Modal({ open, onClose, title, children, size = 'md' }: Props) {
  React.useEffect(() => {
    if (!open) return
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onEsc)
    return () => document.removeEventListener('keydown', onEsc)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-6 animate-fade-in"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="absolute inset-0 bg-bg-base/80 backdrop-blur-sm" />
      <div className={cn(
        'relative bg-bg-elevated border border-border rounded-2xl shadow-floating',
        'w-full', SIZE_CLASS[size], 'animate-rise',
      )}>
        {title && (
          <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border">
            <h3 className="serif text-h1 font-semibold">{title}</h3>
            <button
              onClick={onClose}
              className="w-8 h-8 grid place-items-center rounded-md text-fg-muted hover:text-fg hover:bg-fg/[0.04] transition"
            >
              <X size={18} strokeWidth={1.75} />
            </button>
          </div>
        )}
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}
