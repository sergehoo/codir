import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Bell, Check, CheckCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useAuthStore } from '@/stores/auth'
import type { Notification } from '@/types'
import { cn } from '@/utils/cn'

import { notificationsApi, notificationsKeys } from './api'

function levelColor(level: string) {
  return {
    info: 'bg-info/15 text-info',
    success: 'bg-success/15 text-success',
    warning: 'bg-warning/15 text-warning',
    danger: 'bg-danger/15 text-danger',
  }[level] || 'bg-copper-500/15 text-copper-400'
}

function relTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'à l\'instant'
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`
  return `il y a ${Math.floor(diff / 86400)} j`
}

export function NotificationBell({ className }: { className?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const qc = useQueryClient()
  const token = useAuthStore((s) => s.accessToken)

  const { data: summary } = useQuery({
    queryKey: notificationsKeys.summary(),
    queryFn: () => notificationsApi.summary(),
    refetchInterval: 30_000,
    enabled: !!token,
  })

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationsKeys.all }),
  })
  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationsKeys.all }),
  })

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const unread = summary?.unread ?? 0
  const items = (summary?.latest ?? []) as Notification[]

  return (
    <div ref={ref} className={cn('relative', className)}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-md hover:bg-fg/[0.06] transition"
        title="Notifications"
        aria-label="Notifications"
      >
        <Bell size={18} strokeWidth={1.75} className="text-fg-muted" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-copper-500 text-white text-[10px] font-semibold leading-[18px] text-center">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-96 max-w-[92vw] bg-bg-elevated border border-border rounded-lg shadow-2xl z-50 animate-fade-in-up">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <div>
              <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Notifications</div>
              <div className="text-xs text-fg-subtle mt-0.5">{unread} non lue(s) · {summary?.total ?? 0} au total</div>
            </div>
            {unread > 0 && (
              <button
                onClick={() => markAll.mutate()}
                className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold flex items-center gap-1"
              >
                <CheckCheck size={12} /> Tout lire
              </button>
            )}
          </div>

          <div className="max-h-[60vh] overflow-y-auto">
            {items.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-fg-subtle">
                Boîte vide — bravo !
              </div>
            )}
            {items.map((n) => (
              <div
                key={n.id}
                className={cn(
                  'px-4 py-3 border-b border-border/60 last:border-0 hover:bg-fg/[0.03] transition',
                  !n.seen_at && 'bg-copper-500/[0.04]',
                )}
              >
                <div className="flex items-start gap-3">
                  <span className={cn(
                    'text-2xs uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0 font-semibold',
                    levelColor(n.level),
                  )}>
                    {n.event.replace(/_/g, ' ')}
                  </span>
                  {!n.seen_at && (
                    <button
                      onClick={() => markRead.mutate(n.id)}
                      className="ml-auto text-fg-subtle hover:text-copper-400 transition shrink-0"
                      title="Marquer comme lu"
                    >
                      <Check size={13} />
                    </button>
                  )}
                </div>
                <div className="mt-1.5 text-sm font-medium leading-tight">{n.title}</div>
                {n.body && (
                  <div className="mt-1 text-xs text-fg-muted line-clamp-2">{n.body}</div>
                )}
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <span className="text-2xs text-fg-subtle uppercase tracking-wider">{relTime(n.created_at)}</span>
                  {(n.action_url || n.link_url) && (
                    <Link
                      to={(n.action_url || n.link_url) as any}
                      onClick={() => { setOpen(false); if (!n.seen_at) markRead.mutate(n.id) }}
                      className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold"
                    >
                      Ouvrir →
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="px-4 py-2.5 border-t border-border bg-bg-subtle/30">
            <Link
              to="/notifications"
              onClick={() => setOpen(false)}
              className="text-2xs uppercase tracking-wider text-copper-400 hover:underline font-semibold"
            >
              Tout voir →
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
