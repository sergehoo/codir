import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import * as React from 'react'

import { cn } from '@/utils/cn'

/**
 * Header de page éditorial Atelier.
 *
 *   <SectionHeader
 *     eyebrow="Comité de direction"
 *     title="Réunions"
 *     backTo="/meetings"
 *     actions={<Button>Nouveau</Button>}
 *   />
 */
export function SectionHeader({
  eyebrow,
  title,
  italic,
  backTo,
  backLabel,
  description,
  actions,
  className,
}: {
  eyebrow?: React.ReactNode
  title: React.ReactNode
  /** Affiche en italique cuivre — pattern "Bonjour, *Catherine.*" */
  italic?: React.ReactNode
  backTo?: string
  backLabel?: string
  description?: React.ReactNode
  actions?: React.ReactNode
  className?: string
}) {
  return (
    <header className={cn('px-10 py-8 border-b border-border', className)}>
      {backTo && (
        <Link to={backTo}
              className="inline-flex items-center gap-2 text-2xs uppercase tracking-widest text-fg-muted hover:text-fg transition mb-5">
          <ArrowLeft size={13} /> {backLabel ?? 'Retour'}
        </Link>
      )}
      {eyebrow && (
        <div className="flex items-center gap-3 text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-3">
          <span className="divider-accent" />
          <span>{eyebrow}</span>
        </div>
      )}
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div className="flex-1 min-w-0">
          <h1 className="serif text-editorial leading-[1.1]">
            {title}
            {italic && <> <span className="italic text-copper-400">{italic}</span></>}
          </h1>
          {description && (
            <p className="text-fg-muted mt-3 text-base max-w-2xl">{description}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
      </div>
    </header>
  )
}
