/**
 * DatePickerPopup — sélecteur de date contextuel.
 *
 * Utilisé par SmartMeetingEditor (raccourci Cmd+D) pour insérer
 * une date au format DD/MM/YYYY à la position du curseur. La date
 * est ensuite captée par le parser inline et devient la `due_date`
 * de la tâche/action courante.
 */
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { useEffect, useRef, useState } from 'react'

type Props = {
  open: boolean
  onSelect: (formatted: string) => void
  onClose: () => void
  /** Position absolue à l'écran (haut-gauche du popup). */
  anchor?: { top: number; left: number } | null
}

const PRESETS: { label: string; offsetDays: number }[] = [
  { label: "Aujourd'hui",    offsetDays: 0 },
  { label: 'Demain',         offsetDays: 1 },
  { label: 'Dans 3 jours',   offsetDays: 3 },
  { label: 'Dans 1 semaine', offsetDays: 7 },
  { label: 'Dans 2 semaines', offsetDays: 14 },
  { label: 'Dans 1 mois',    offsetDays: 30 },
]

function formatDDMMYYYY(d: Date) {
  return format(d, 'dd/MM/yyyy')
}

export function DatePickerPopup({ open, onSelect, onClose, anchor }: Props) {
  const today = new Date()
  const todayIso = format(today, 'yyyy-MM-dd')
  const [iso, setIso] = useState(todayIso)
  const popupRef = useRef<HTMLDivElement>(null)

  // Reset à chaque ouverture
  useEffect(() => {
    if (open) setIso(todayIso)
  }, [open, todayIso])

  // Esc → close
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Click outside → close
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    // Tick to skip the same click that opened the popup
    const id = window.setTimeout(() => document.addEventListener('mousedown', onDown), 0)
    return () => {
      window.clearTimeout(id)
      document.removeEventListener('mousedown', onDown)
    }
  }, [open, onClose])

  if (!open) return null

  const handlePreset = (offset: number) => {
    const d = new Date()
    d.setDate(d.getDate() + offset)
    onSelect(formatDDMMYYYY(d))
  }
  const handleCustom = () => {
    if (!iso) return
    const [y, m, dd] = iso.split('-').map((n) => parseInt(n, 10))
    if (!y || !m || !dd) return
    onSelect(formatDDMMYYYY(new Date(y, m - 1, dd)))
  }

  const position = anchor
    ? { position: 'fixed' as const, top: anchor.top, left: anchor.left, zIndex: 9999 }
    : { position: 'fixed' as const, top: '50%', left: '50%', transform: 'translate(-50%,-50%)', zIndex: 9999 }

  return (
    <div
      ref={popupRef}
      style={position}
      className="bg-bg-elevated border border-border rounded-lg shadow-2xl w-72 overflow-hidden animate-fade-in"
      role="dialog"
      aria-label="Sélectionner une échéance"
    >
      <div className="px-3 py-2 text-2xs uppercase tracking-widest text-fg-muted bg-bg-subtle/40 border-b border-border">
        Insérer une échéance
      </div>

      {/* Raccourcis */}
      <ul className="py-1">
        {PRESETS.map((p) => {
          const d = new Date()
          d.setDate(d.getDate() + p.offsetDays)
          return (
            <li
              key={p.label}
              onClick={() => handlePreset(p.offsetDays)}
              className="px-3 py-1.5 cursor-pointer flex items-center justify-between hover:bg-copper-500/10 text-sm transition"
            >
              <span>{p.label}</span>
              <span className="text-2xs text-fg-subtle tabular">
                {format(d, 'EEE d MMM', { locale: fr })}
              </span>
            </li>
          )
        })}
      </ul>

      {/* Saisie libre */}
      <div className="border-t border-border p-3 space-y-2">
        <label className="text-2xs uppercase tracking-wider text-fg-muted font-semibold">
          Date personnalisée
        </label>
        <input
          type="date"
          value={iso}
          onChange={(e) => setIso(e.target.value)}
          className="w-full px-2 py-1.5 rounded-md border border-border bg-bg-base text-sm tabular"
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="text-2xs uppercase tracking-wider text-fg-muted px-2 py-1 rounded hover:bg-bg-base"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={handleCustom}
            className="text-2xs uppercase tracking-wider bg-copper-500 hover:bg-copper-400 text-white px-3 py-1 rounded font-semibold"
          >
            Insérer
          </button>
        </div>
      </div>
    </div>
  )
}
