import { useNavigate } from '@tanstack/react-router'
import {
  ArrowRight, Bell, CheckSquare, FileText, Gauge,
  LayoutDashboard, LogOut, Plus, Scale, Search, Users,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useAuthStore } from '@/stores/auth'
import { cn } from '@/utils/cn'

type Action = {
  id: string
  label: string
  hint?: string
  icon: typeof LayoutDashboard
  group: 'Navigation' | 'Actions' | 'Compte'
  to?: string
  run?: () => void
  shortcut?: string
}

/** Command Palette ⌘K — recherche fuzzy + navigation rapide. */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const logout = useAuthStore((s) => s.logout)
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // Reset au open
  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIdx(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Liste d'actions
  const actions: Action[] = useMemo(() => ([
    { id: 'nav-dashboard',    label: 'Cockpit',                icon: LayoutDashboard, group: 'Navigation', to: '/',              shortcut: 'G D' },
    { id: 'nav-meetings',     label: 'Réunions',               icon: Gauge,           group: 'Navigation', to: '/meetings',      shortcut: 'G M' },
    { id: 'nav-decisions',    label: 'Décisions',              icon: Scale,           group: 'Navigation', to: '/decisions',     shortcut: 'G C' },
    { id: 'nav-plans',        label: "Plans d'action",         icon: CheckSquare,     group: 'Navigation', to: '/action-plans',  shortcut: 'G P' },
    { id: 'nav-mytasks',      label: 'Mes tâches',             icon: Users,           group: 'Navigation', to: '/my-tasks',      shortcut: 'G T' },
    { id: 'nav-docs',         label: 'Documents',              icon: FileText,        group: 'Navigation', to: '/documents' },
    { id: 'nav-notifs',       label: 'Notifications',          icon: Bell,            group: 'Navigation', to: '/notifications' },

    { id: 'act-new-meeting',  label: 'Nouvelle réunion',       icon: Plus, group: 'Actions', to: '/meetings/new', shortcut: '⌘ N', hint: 'Convoquer un comité' },

    { id: 'acc-profile',      label: 'Mon profil',             icon: Users,           group: 'Compte', to: '/profile' },
    { id: 'acc-logout',       label: 'Se déconnecter',         icon: LogOut,          group: 'Compte', run: () => { logout(); window.location.href = '/login' } },
  ]), [logout])

  // Filtrage fuzzy
  const filtered = useMemo(() => {
    if (!query.trim()) return actions
    const q = query.toLowerCase()
    return actions.filter((a) =>
      a.label.toLowerCase().includes(q)
      || (a.hint && a.hint.toLowerCase().includes(q))
      || a.group.toLowerCase().includes(q)
    )
  }, [actions, query])

  // Reset selection
  useEffect(() => { setSelectedIdx(0) }, [filtered.length])

  // Keyboard nav
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1)) }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setSelectedIdx((i) => Math.max(i - 1, 0)) }
      if (e.key === 'Enter') {
        e.preventDefault()
        const a = filtered[selectedIdx]
        if (a) run(a)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, filtered, selectedIdx])

  function run(a: Action) {
    onClose()
    if (a.run) a.run()
    else if (a.to) navigate({ to: a.to as any })
  }

  if (!open) return null

  // Grouper
  const groups: Record<string, Action[]> = {}
  filtered.forEach((a) => { (groups[a.group] ??= []).push(a) })

  let runningIdx = 0

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-start pt-[15vh] p-6 animate-fade-in"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="absolute inset-0 bg-bg-base/85 backdrop-blur-md" />
      <div className="relative w-full max-w-2xl bg-bg-elevated border border-border rounded-2xl shadow-floating overflow-hidden animate-rise">
        {/* Search bar */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
          <Search size={18} strokeWidth={1.75} className="text-fg-subtle" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher une page, une action…"
            className="flex-1 bg-transparent outline-none text-base placeholder:text-fg-subtle"
          />
          <kbd className="text-2xs font-mono text-fg-subtle border border-border bg-bg-base px-2 py-0.5 rounded">Esc</kbd>
        </div>

        {/* Results */}
        <div className="max-h-[55vh] overflow-y-auto py-2">
          {filtered.length === 0 && (
            <div className="px-5 py-12 text-center text-fg-subtle text-sm">
              Aucun résultat pour <span className="text-fg">« {query} »</span>
            </div>
          )}
          {Object.entries(groups).map(([group, items]) => (
            <div key={group} className="py-1">
              <div className="px-5 py-2 text-2xs uppercase tracking-widest text-fg-subtle font-semibold flex items-center gap-2">
                <span className="divider-accent" /> {group}
              </div>
              {items.map((a) => {
                const idx = runningIdx++
                const active = idx === selectedIdx
                return (
                  <button
                    key={a.id}
                    onClick={() => run(a)}
                    onMouseEnter={() => setSelectedIdx(idx)}
                    className={cn(
                      'w-full flex items-center gap-3 px-5 py-2.5 text-left transition',
                      active ? 'bg-copper-500/10 text-copper-400' : 'text-fg hover:bg-fg/[0.04]',
                    )}
                  >
                    <a.icon size={16} strokeWidth={1.75} className={active ? 'text-copper-400' : 'text-fg-muted'} />
                    <span className="flex-1 text-sm font-medium">{a.label}</span>
                    {a.hint && <span className="text-2xs text-fg-subtle">{a.hint}</span>}
                    {a.shortcut && (
                      <kbd className="text-2xs font-mono text-fg-subtle border border-border bg-bg-base px-1.5 py-0.5 rounded">
                        {a.shortcut}
                      </kbd>
                    )}
                    {active && <ArrowRight size={13} className="text-copper-400" />}
                  </button>
                )
              })}
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="px-5 py-3 border-t border-border bg-bg-subtle/50 flex items-center justify-between gap-4 text-2xs text-fg-subtle">
          <div className="flex items-center gap-3">
            <span><kbd className="font-mono">↑↓</kbd> Naviguer</span>
            <span><kbd className="font-mono">↵</kbd> Sélectionner</span>
          </div>
          <span>Kaydan · CODIR Beta</span>
        </div>
      </div>
    </div>
  )
}

/** Hook qui écoute ⌘K / Ctrl+K et toggle l'ouverture. */
export function useCommandPaletteHotkey(setOpen: (v: boolean) => void) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [setOpen])
}
