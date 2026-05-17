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

/**
 * Modal sobre éditorial avec overlay flouté + scroll interne si contenu long.
 *
 * Le body est cappé à `max-h-[calc(90vh-100px)]` (90% viewport - header) et
 * scrolle si nécessaire. Le header reste fixe en haut. Le padding viewport
 * `p-4` empêche le modal de coller aux bords sur mobile.
 */
export function Modal({ open, onClose, title, children, size = 'md' }: Props) {
  React.useEffect(() => {
    if (!open) return
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onEsc)
    // Lock body scroll quand le modal est ouvert
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onEsc)
      document.body.style.overflow = prevOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 sm:p-6 animate-fade-in overflow-y-auto"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="absolute inset-0 bg-bg-base/80 backdrop-blur-sm" />
      <div
        className={cn(
          'relative bg-bg-elevated border border-border rounded-2xl shadow-floating',
          'w-full my-auto flex flex-col max-h-[calc(100vh-2rem)]',
          SIZE_CLASS[size],
          'animate-rise',
        )}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border shrink-0 bg-bg-elevated rounded-t-2xl">
            <h3 className="serif text-h1 font-semibold truncate pr-3">{title}</h3>
            <button
              onClick={onClose}
              className="w-8 h-8 grid place-items-center rounded-md text-fg-muted hover:text-fg hover:bg-fg/[0.04] transition shrink-0"
              aria-label="Fermer"
            >
              <X size={18} strokeWidth={1.75} />
            </button>
          </div>
        )}
        <div className="p-6 overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  )
}
