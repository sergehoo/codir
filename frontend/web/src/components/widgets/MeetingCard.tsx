import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { CalendarClock, MapPin, Users, Video } from 'lucide-react'

import type { Meeting } from '@/types'
import { StatusBadge } from './StatusBadge'

export function MeetingCard({ m }: { m: Meeting }) {
  return (
    <Link
      to="/meetings/$id"
      params={{ id: m.id }}
      className="card p-4 flex gap-4 hover:border-blue-300 hover:shadow-sm transition"
    >
      <div className="w-14 h-14 rounded-lg bg-blue-50 text-blue-700 grid place-items-center shrink-0">
        <CalendarClock size={22} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="font-semibold truncate">{m.title}</span>
          <StatusBadge status={m.status} className="ml-auto" />
        </div>
        <div className="text-xs text-slate-500 mt-1">
          {format(new Date(m.scheduled_start), 'EEE d MMM yyyy · HH:mm', { locale: fr })} —{' '}
          {format(new Date(m.scheduled_end), 'HH:mm', { locale: fr })}
        </div>
        <div className="flex flex-wrap gap-3 mt-2 text-xs text-slate-500">
          {m.location && (
            <span className="inline-flex items-center gap-1">
              <MapPin size={12} /> {m.location}
            </span>
          )}
          {m.video_url && (
            <span className="inline-flex items-center gap-1">
              <Video size={12} /> Visio
            </span>
          )}
          <span className="inline-flex items-center gap-1">
            <Users size={12} /> {m.participants_count ?? 0} participants
          </span>
        </div>
      </div>
    </Link>
  )
}
