import * as React from 'react'
import { cn } from '@/utils/cn'

/** Empty state éditorial — illustration vectorielle, titre, sous-titre, CTA optionnel. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>
  title: string
  description?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('card p-12 text-center', className)}>
      {Icon && (
        <div className="inline-grid place-items-center w-14 h-14 rounded-full bg-fg/[0.04] mb-4">
          <Icon size={22} strokeWidth={1.5} className="text-fg-subtle" />
        </div>
      )}
      <h3 className="serif text-h2 font-medium text-fg mb-2">{title}</h3>
      {description && (
        <p className="text-fg-muted text-sm max-w-md mx-auto leading-relaxed">{description}</p>
      )}
      {action && <div className="mt-6 flex items-center justify-center gap-2">{action}</div>}
    </div>
  )
}
