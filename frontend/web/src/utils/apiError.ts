/**
 * Extraction d'un message lisible depuis une erreur axios / DRF.
 *
 * Le piège : la plupart des écrans faisaient
 *   `err?.response?.data?.detail || 'Échec de la création'`
 *
 * Or DRF ne renvoie `detail` que pour les erreurs de permission (403) et
 * les 404. Les erreurs de VALIDATION (400) arrivent sous la forme d'un
 * dictionnaire par champ :
 *
 *   { "title": ["Ensure this field has no more than 300 characters."],
 *     "due_date": ["Date has wrong format."] }
 *
 * Sans clé `detail`, tout cela tombait dans le message générique — et
 * l'utilisateur ne pouvait pas savoir quel champ posait problème, ni le
 * développeur diagnostiquer à distance.
 */

/** Libellés FR pour les champs les plus exposés dans les formulaires. */
const FIELD_LABELS: Record<string, string> = {
  title: 'Titre',
  description_md: 'Description',
  due_date: 'Échéance',
  priority: 'Priorité',
  assignee: 'Responsable principal',
  co_assignees: 'Co-responsables',
  owner: 'Responsable',
  subsidiary: 'Filiale',
  direction: 'Direction',
  decision: 'Décision',
  status: 'Statut',
  effort_estimate_hours: 'Charge estimée',
  parent: 'Tâche parente',
  non_field_errors: '',
}

function flatten(value: unknown): string[] {
  if (value == null) return []
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(flatten)
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).flatMap(flatten)
  }
  return [String(value)]
}

/**
 * Retourne un message affichable, en privilégiant la précision.
 *
 * @param err      erreur capturée (axios ou autre)
 * @param fallback message si rien d'exploitable n'est trouvé
 */
export function apiError(err: unknown, fallback = 'Une erreur est survenue'): string {
  const anyErr = err as any
  const res = anyErr?.response
  const data = res?.data

  // 1. Erreur réseau : pas de réponse du tout.
  if (!res) {
    if (anyErr?.code === 'ECONNABORTED') {
      return 'Délai dépassé — le serveur met trop de temps à répondre.'
    }
    if (anyErr?.message === 'Network Error') {
      return 'Connexion au serveur impossible. Vérifiez votre réseau.'
    }
  }

  // 2. Réponse texte brute (page d'erreur HTML d'un proxy, par ex.).
  if (typeof data === 'string' && data.trim() && !data.trim().startsWith('<')) {
    return data.slice(0, 300)
  }

  if (data && typeof data === 'object') {
    // 3. `detail` — permissions, 404, erreurs métier explicites.
    //    Peut exceptionnellement être un objet : on le traite alors
    //    comme le reste plutôt que de perdre l'information.
    const detail = (data as any).detail
    if (typeof detail === 'string' && detail.trim()) return detail

    // 3bis. Erreurs racine sous forme de liste (ListSerializer DRF) :
    //       sans ce cas, Object.entries produirait « 0 : message ».
    if (Array.isArray(data)) {
      const flat = flatten(data).filter(Boolean)
      if (flat.length > 0) return flat.join(' · ').slice(0, 400)
    }

    // 4. Erreurs de validation par champ.
    const parts: string[] = []
    for (const [field, raw] of Object.entries(data as Record<string, unknown>)) {
      if (field === 'detail' && typeof detail === 'string') continue
      // Ignore les messages vides : `{"title": [""]}` ne doit pas
      // produire un « Titre : » sans contenu.
      const messages = flatten(raw).map((m) => m.trim()).filter(Boolean)
      if (messages.length === 0) continue
      const label = FIELD_LABELS[field] ?? field
      parts.push(label ? `${label} : ${messages.join(' ')}` : messages.join(' '))
    }
    if (parts.length > 0) return parts.join(' · ').slice(0, 400)
  }

  // 5. Statut HTTP seul — au moins on distingue les familles d'erreur.
  const status = res?.status
  if (status === 403) return "Vous n'avez pas les droits pour cette action."
  if (status === 401) return 'Session expirée. Reconnectez-vous.'
  if (status === 413) return 'Contenu trop volumineux.'
  if (status && status >= 500) {
    return `Erreur serveur (${status}). Réessayez dans un instant.`
  }

  return fallback
}
