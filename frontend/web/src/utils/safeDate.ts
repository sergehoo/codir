// Helpers de formatage de dates tolérants — évitent les crashes
// `RangeError: Invalid time value` quand date-fns reçoit null/undefined/string mal formée.
//
// À utiliser PARTOUT à la place de `format(new Date(x), ...)` dès qu'on
// formate un champ qui peut être null côté backend (DateTimeField avec null=True).
import { format, parseISO, type FormatOptions } from 'date-fns'
import { fr } from 'date-fns/locale'

/** Valeur affichée quand la date est manquante ou invalide. */
const FALLBACK = '—'

/**
 * Convertit une valeur "date" (string ISO, Date, null, undefined) en Date valide,
 * ou null si non parsable.
 */
export function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null
  if (value instanceof Date) {
    return isFinite(value.getTime()) ? value : null
  }
  // string : on tente parseISO d'abord (le plus rapide + strict), puis new Date.
  try {
    const d = parseISO(value)
    if (isFinite(d.getTime())) return d
  } catch { /* ignore */ }
  try {
    const d = new Date(value)
    if (isFinite(d.getTime())) return d
  } catch { /* ignore */ }
  return null
}

/**
 * Formate une date avec date-fns. Retourne `fallback` si la valeur est
 * null/undefined/invalide. Ne throw JAMAIS.
 *
 * @example
 *   safeFormat(meeting.scheduled_start, "EEEE d MMMM yyyy", { locale: fr })
 *   safeFormat(task.due_date, "dd/MM/yyyy", { fallback: "Non définie" })
 */
export function safeFormat(
  value: string | Date | null | undefined,
  formatStr: string,
  opts?: FormatOptions & { fallback?: string },
): string {
  const d = toDate(value)
  if (!d) return opts?.fallback ?? FALLBACK
  try {
    const { fallback: _f, ...formatOpts } = opts ?? {}
    return format(d, formatStr, { locale: fr, ...formatOpts })
  } catch {
    return opts?.fallback ?? FALLBACK
  }
}

/** Variante courte : `d MMM yyyy` (locale FR par défaut). */
export function safeShortDate(
  value: string | Date | null | undefined,
  fallback: string = FALLBACK,
): string {
  return safeFormat(value, 'd MMM yyyy', { fallback })
}

/** Variante courte avec heure : `d MMM yyyy à HH:mm`. */
export function safeShortDateTime(
  value: string | Date | null | undefined,
  fallback: string = FALLBACK,
): string {
  return safeFormat(value, "d MMM yyyy 'à' HH:mm", { fallback })
}
