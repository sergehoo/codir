/**
 * Popup d'autocomplete @ — affiche les candidats sous le curseur Tiptap.
 */
import { forwardRef, useEffect, useImperativeHandle, useState } from 'react'

import type { MentionCandidate } from '../api'

type Props = {
  items: MentionCandidate[]
  command: (item: { id: string; label: string }) => void
}

export const MentionAutocomplete = forwardRef((props: Props, ref) => {
  const [selected, setSelected] = useState(0)

  useEffect(() => setSelected(0), [props.items])

  useImperativeHandle(ref, () => ({
    onKeyDown(e: KeyboardEvent) {
      if (e.key === 'ArrowDown') {
        setSelected((s) => (s + 1) % Math.max(props.items.length, 1))
        return true
      }
      if (e.key === 'ArrowUp') {
        setSelected((s) => (s - 1 + props.items.length) % Math.max(props.items.length, 1))
        return true
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        const item = props.items[selected]
        if (item) {
          props.command({ id: item.id, label: item.full_name })
          return true
        }
      }
      return false
    },
  }))

  if (!props.items.length) {
    return (
      <div className="bg-bg-elevated border border-border rounded-lg shadow-2xl px-3 py-2 text-2xs text-fg-subtle uppercase tracking-wider">
        Aucun membre trouvé
      </div>
    )
  }

  return (
    <div className="bg-bg-elevated border border-border rounded-lg shadow-2xl w-72 overflow-hidden">
      <div className="px-3 py-2 text-2xs uppercase tracking-widest text-fg-muted bg-bg-subtle/40 border-b border-border">
        Mentionner un membre
      </div>
      <ul className="max-h-64 overflow-auto">
        {props.items.slice(0, 8).map((u, i) => (
          <li
            key={u.id}
            onMouseEnter={() => setSelected(i)}
            onClick={() => props.command({ id: u.id, label: u.full_name })}
            className={`px-3 py-2 cursor-pointer flex items-center gap-3 transition ${
              i === selected ? 'bg-copper-500/15 text-copper-400' : 'text-fg hover:bg-fg/[0.04]'
            }`}
          >
            <div className="w-7 h-7 rounded-full bg-copper-gradient grid place-items-center text-white text-2xs font-medium shrink-0">
              {(u.first_name?.[0] || u.email[0]).toUpperCase()}
              {(u.last_name?.[0] || '').toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{u.full_name}</div>
              <div className="text-2xs text-fg-subtle truncate uppercase tracking-wider">
                {u.is_executive ? 'Executive' : 'Member'} · {u.email}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
})

MentionAutocomplete.displayName = 'MentionAutocomplete'
