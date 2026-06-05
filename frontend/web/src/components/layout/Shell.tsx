import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import {
  Bell, Building2, CheckSquare, Gauge, LayoutDashboard, LogOut,
  RotateCcw, Scale, ScrollText, Search, User as UserIcon, Users,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { CommandPalette, useCommandPaletteHotkey } from '@/components/layout/CommandPalette'
import { KaydanLogo } from '@/components/widgets/KaydanLogo'
import { ThemeToggle } from '@/components/widgets/ThemeToggle'
import { notificationsApi } from '@/features/notifications/api'
import { NotificationBell } from '@/features/notifications/NotificationBell'
import { useAuthStore } from '@/stores/auth'
import { cn } from '@/utils/cn'

const NAV: { to: string; label: string; icon: typeof Gauge }[] = [
  { to: '/',              label: 'Cockpit',          icon: LayoutDashboard },
  { to: '/meetings',      label: 'Réunions',         icon: Gauge },
  { to: '/decisions',     label: 'Décisions',        icon: Scale },
  { to: '/action-plans',  label: 'Suivi Projets/Dossiers',  icon: CheckSquare },
  { to: '/my-tasks',      label: 'Mes tâches',       icon: Users },
//{ to: '/documents',     label: 'Documents',        icon: FileText },
]

const SETTINGS_NAV: { to: string; label: string; icon: typeof Gauge; adminOnly?: boolean }[] = [
  { to: '/settings/members',        label: 'Membres CODIR',     icon: Users },
  { to: '/settings/subsidiaries',   label: 'Filiales',          icon: Building2 },
  { to: '/settings/meeting-series', label: 'Séries récurrentes', icon: RotateCcw },
  { to: '/settings/logs',           label: 'Journal d\'activité', icon: ScrollText, adminOnly: true },
  { to: '/profile',                 label: 'Mon profil',        icon: UserIcon },
]

// Détection "actif" robuste : match exact OU sous-route (`/foo/bar`),
// PAS un préfixe arbitraire (`/foo-bar` ne doit pas matcher `/foo`).
function isActivePath(currentPath: string, to: string): boolean {
  if (to === '/') return currentPath === '/'
  return currentPath === to || currentPath.startsWith(to + '/')
}

export function Shell() {
  // ⚠️ useRouter() ne s'abonne pas aux changements — on utilise useRouterState
  // avec un selector pour ne re-render que sur changement de pathname.
  const path = useRouterState({ select: (s) => s.location.pathname })
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const accessToken = useAuthStore((s) => s.accessToken)
  const { data: unread } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => notificationsApi.unreadCount(),
    refetchInterval: 30_000,
    enabled: !!accessToken,
  })

  // Command Palette ⌘K
  const [paletteOpen, setPaletteOpen] = useState(false)
  useCommandPaletteHotkey(setPaletteOpen)

  return (
    <div className="flex h-screen overflow-hidden bg-bg-base text-fg">
      {/* ─── Sidebar — papier exécutif feutré ────────────────── */}
      <aside className="w-64 shrink-0 bg-bg-subtle border-r border-border flex flex-col">

        {/* Header sidebar — logo Kaydan en bannière + produit Codir en sous-titre */}
        <div className="px-5 pt-5 pb-4 border-b border-border space-y-4">
          {/* Logo Kaydan officiel — fond transparent */}
          <div className="flex items-center justify-center">
            <KaydanLogo variant="full" className="h-14 w-auto" />
          </div>
          {/* Produit */}
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="serif text-base font-semibold leading-none">CODIR</div>
              <div className="text-2xs uppercase tracking-widest text-fg-subtle mt-1">
                Executive Platform
              </div>
            </div>
            <span className="text-2xs font-bold text-copper-400 bg-copper-500/10 border border-copper-500/30 px-1.5 py-0.5 rounded uppercase tracking-wider">
              Beta
            </span>
          </div>
        </div>

        {/* Search */}
        <div className="px-4 py-4">
          <button
            onClick={() => setPaletteOpen(true)}
            className="w-full inline-flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg border border-border bg-bg-elevated hover:border-copper-500/30 hover:bg-copper-500/5 text-fg-muted text-xs transition-all duration-250 ease-editorial"
          >
            <Search size={14} />
            <span className="flex-1 text-left">Rechercher…</span>
            <kbd className="px-1.5 py-0.5 rounded bg-bg-base border border-border text-2xs font-mono">⌘K</kbd>
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-4 space-y-0.5 overflow-auto">
          <div className="text-2xs uppercase tracking-widest text-fg-subtle px-3 py-3 font-semibold flex items-center gap-2.5">
            <span className="divider-accent" /> Pilotage
          </div>
          {NAV.map((n) => {
            const active = isActivePath(path, n.to)
            return (
              <Link
                key={n.to} to={n.to}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-250 ease-editorial relative text-sm',
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-copper-500/50 focus-visible:ring-offset-1 focus-visible:ring-offset-bg-subtle',
                  active
                    ? 'bg-copper-500/10 text-copper-400 font-medium'
                    : 'text-fg-muted hover:bg-fg/[0.04] hover:text-fg',
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-copper-500 rounded-r" />
                )}
                <n.icon size={16} className="shrink-0" strokeWidth={1.75} />
                <span className="flex-1">{n.label}</span>
              </Link>
            )
          })}

          <div className="text-2xs uppercase tracking-widest text-fg-subtle px-3 pt-7 pb-3 font-semibold flex items-center gap-2.5">
            <span className="divider-accent" /> Inbox
          </div>
          {(() => {
            const active = isActivePath(path, '/notifications')
            return (
              <Link
                to="/notifications"
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-250 ease-editorial relative text-sm',
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-copper-500/50 focus-visible:ring-offset-1 focus-visible:ring-offset-bg-subtle',
                  active
                    ? 'bg-copper-500/10 text-copper-400 font-medium'
                    : 'text-fg-muted hover:bg-fg/[0.04] hover:text-fg',
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-copper-500 rounded-r" />
                )}
                <Bell size={16} className="shrink-0" strokeWidth={1.75} />
                <span className="flex-1">Notifications</span>
                {(unread?.unread ?? 0) > 0 && (
                  <span className="text-2xs font-medium bg-copper-500 text-white rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                    {unread!.unread > 99 ? '99+' : unread!.unread}
                  </span>
                )}
              </Link>
            )
          })()}

          {/* ─── Paramètres ─── */}
          <div className="text-2xs uppercase tracking-widest text-fg-subtle px-3 pt-7 pb-3 font-semibold flex items-center gap-2.5">
            <span className="divider-accent" /> Paramètres
          </div>
          {SETTINGS_NAV.filter((n) => !n.adminOnly || user?.is_executive).map((n) => {
            const active = isActivePath(path, n.to)
            return (
              <Link
                key={n.to} to={n.to}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-250 ease-editorial relative text-sm',
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-copper-500/50 focus-visible:ring-offset-1 focus-visible:ring-offset-bg-subtle',
                  active
                    ? 'bg-copper-500/10 text-copper-400 font-medium'
                    : 'text-fg-muted hover:bg-fg/[0.04] hover:text-fg',
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-copper-500 rounded-r" />
                )}
                <n.icon size={16} className="shrink-0" strokeWidth={1.75} />
                <span className="flex-1">{n.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* Footer sidebar — user card */}
        <div className="p-4 border-t border-border space-y-3">
          {user && (
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-copper-gradient grid place-items-center text-white font-medium text-xs shrink-0">
                {(user.first_name?.[0] || user.email[0]).toUpperCase()}
                {(user.last_name?.[0] || '').toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-medium text-xs truncate">{user.full_name || user.email}</div>
                <div className="text-2xs text-fg-subtle uppercase tracking-wider">
                  {user.is_executive ? 'Executive' : 'Member'}
                </div>
              </div>
              <ThemeToggle />
            </div>
          )}
          <button
            onClick={() => { logout(); window.location.href = '/login' }}
            className="w-full inline-flex items-center justify-center gap-1.5 py-2 rounded-md text-fg-muted hover:text-danger hover:bg-danger/5 transition text-2xs uppercase tracking-wider font-semibold"
          >
            <LogOut size={11} /> Déconnexion
          </button>
        </div>
      </aside>

      {/* ─── Main ────────────────────────────────────────── */}
      <main className="flex-1 overflow-auto bg-bg-base relative">
        {/* Topbar flottante — bell + raccourcis */}
        <div className="sticky top-0 z-30 flex items-center justify-end gap-1 px-6 py-3 bg-bg-base/95 backdrop-blur-md border-b border-border shadow-sm">
          <NotificationBell />
        </div>
        <Outlet />
      </main>

      {/* Command Palette ⌘K — overlay global */}
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
