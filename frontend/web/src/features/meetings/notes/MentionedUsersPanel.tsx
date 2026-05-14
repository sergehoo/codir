import { AtSign } from 'lucide-react'

import type { MeetingNoteMention } from '../api'

export function MentionedUsersPanel({ mentions }: { mentions: MeetingNoteMention[] }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <AtSign size={13} className="text-copper-400" />
        <h3 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
          Membres mentionnés
        </h3>
        <span className="chip-quiet">{mentions.length}</span>
      </div>

      {mentions.length === 0 && (
        <div className="text-2xs text-fg-subtle uppercase tracking-wider px-1 py-3">
          Tapez <code className="text-copper-400 font-mono">@</code> pour mentionner un membre.
        </div>
      )}

      <ul className="space-y-1.5">
        {mentions.map((m) => (
          <li key={m.id} className="flex items-center gap-3 px-2 py-1.5 rounded hover:bg-fg/[0.03] transition">
            {m.user_detail ? (
              <>
                <div className="w-7 h-7 rounded-full bg-copper-gradient grid place-items-center text-white text-2xs font-medium shrink-0">
                  {(m.user_detail.first_name?.[0] || '?').toUpperCase()}
                  {(m.user_detail.last_name?.[0] || '').toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{m.user_detail.full_name}</div>
                  <div className="text-2xs text-fg-subtle uppercase tracking-wider">
                    {m.occurrences} mention(s)
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="w-7 h-7 rounded-full bg-fg/10 grid place-items-center text-fg-subtle text-2xs font-medium shrink-0">?</div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate text-fg-muted">{m.raw_text}</div>
                  <div className="text-2xs text-warning uppercase tracking-wider">Non résolu</div>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
