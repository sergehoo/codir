/**
 * OrganizationSwitcher — dropdown affiché dans la topbar.
 *
 * - Affiche le logo + nom de l'org courante
 * - Au click : liste de toutes les organisations accessibles
 * - Sélection → switch via le hook useOrganizationSwitch
 * - Recherche si > 5 organisations
 * - Indicateur visuel sur l'org courante
 */
import { Building2, Check, ChevronDown, Loader2, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useCurrentMembership, useMemberships } from '@/stores/auth'
import { cn } from '@/utils/cn'

import { useOrganizationSwitch } from '../useOrganizationSwitch'
import { OrganizationAvatar } from './OrganizationAvatar'

export function OrganizationSwitcher() {
  // useMemberships garantit un tableau même si l'état persisté est corrompu.
  const memberships = useMemberships()
  const current = useCurrentMembership()
  const switchOrg = useOrganizationSwitch()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement | null>(null)

  // Fermer au click extérieur + Esc
  useEffect(() => {
    if (!open) return
    function onClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  const filtered = useMemo(() => {
    if (!search.trim()) return memberships
    const q = search.toLowerCase()
    return memberships.filter((m) =>
      m.organization_name.toLowerCase().includes(q)
      || m.organization_slug.toLowerCase().includes(q),
    )
  }, [memberships, search])

  // Si l'utilisateur n'a qu'une seule organisation, on n'affiche pas le switcher
  // (UX cleaner). On affiche juste un badge non interactif.
  if (memberships.length === 0) return null
  if (memberships.length === 1 && current) {
    return (
      <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-md border border-border bg-bg-elevated text-xs">
        <OrganizationAvatar membership={current} size={20} />
        <span className="font-medium">{current.organization_name}</span>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'inline-flex items-center gap-2 px-3 py-1.5 rounded-md',
          'border border-border bg-bg-elevated hover:border-copper-500/40',
          'text-sm font-medium transition',
        )}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {current ? (
          <>
            <OrganizationAvatar membership={current} size={20} />
            <span className="truncate max-w-[160px]">{current.organization_name}</span>
          </>
        ) : (
          <>
            <Building2 size={14} className="text-fg-muted" />
            <span className="text-fg-muted">Sélectionner une organisation</span>
          </>
        )}
        <ChevronDown
          size={13}
          className={cn(
            'text-fg-muted transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>

      {open && (
        <div
          role="listbox"
          className={cn(
            'absolute right-0 mt-2 w-80 rounded-lg border border-border bg-bg-base',
            'shadow-2xl overflow-hidden z-50 animate-fade-in-up',
          )}
        >
          <div className="px-3 py-2 border-b border-border bg-bg-subtle">
            <div className="text-2xs uppercase tracking-wider text-fg-muted font-semibold">
              Mes organisations ({memberships.length})
            </div>
          </div>

          {/* Recherche si > 5 orgs */}
          {memberships.length > 5 && (
            <div className="relative border-b border-border">
              <Search
                size={13}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle"
              />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher…"
                autoFocus
                className="w-full pl-9 pr-3 py-2 text-sm bg-transparent outline-none border-0"
              />
            </div>
          )}

          <ul className="max-h-80 overflow-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-3 py-4 text-center text-xs text-fg-muted italic">
                Aucune organisation ne correspond à "{search}".
              </li>
            ) : (
              filtered.map((m) => {
                const isActive = m.is_current
                  || (current?.organization_id === m.organization_id)
                return (
                  <li key={m.organization_id}>
                    <button
                      type="button"
                      onClick={() => {
                        if (!isActive) switchOrg.mutate(m)
                        setOpen(false)
                      }}
                      disabled={switchOrg.isPending}
                      className={cn(
                        'w-full text-left flex items-center gap-3 px-3 py-2.5',
                        'hover:bg-copper-500/5 transition',
                        isActive && 'bg-copper-500/10',
                      )}
                    >
                      <OrganizationAvatar membership={m} size={28} />
                      <div className="flex-1 min-w-0">
                        <div className={cn(
                          'text-sm truncate',
                          isActive ? 'font-semibold text-copper-400' : 'font-medium',
                        )}>
                          {m.organization_name}
                        </div>
                        <div className="text-2xs text-fg-muted uppercase tracking-wider mt-0.5">
                          {m.role_label}
                          {m.subsidiary_name && ` · ${m.subsidiary_name}`}
                        </div>
                      </div>
                      {isActive && (
                        <Check size={14} className="text-copper-400 shrink-0" />
                      )}
                      {switchOrg.isPending && switchOrg.variables &&
                       (typeof switchOrg.variables === 'string'
                         ? switchOrg.variables === m.organization_id
                         : (switchOrg.variables as any).organization_id === m.organization_id) && (
                        <Loader2 size={14} className="animate-spin text-copper-400 shrink-0" />
                      )}
                    </button>
                  </li>
                )
              })
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
