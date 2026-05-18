/**
 * Parser frontend (côté affichage live) — extrait des structures CODIR depuis
 * une liste de lignes de texte (texte brut de l'éditeur).
 *
 * Cette logique fait le miroir du parser backend `notes_services.py`. Elle est
 * utilisée pour afficher en temps réel les badges et la liste des détections
 * dans les panneaux latéraux SANS attendre l'autosave.
 *
 * Synchronisation finale assurée par le backend lors de l'autosave.
 */

export type ParsedAction = {
  title: string
  raw_line: string
  mention: string | null
  order: number
}

export type ParsedDecision = {
  title: string
  raw_line: string
  order: number
  actions: ParsedAction[]
}

export type LocalParseResult = {
  decisions: ParsedDecision[]
  orphan_actions: ParsedAction[]
  mentions: string[]
}

const LINE_DECISION = /^\s*#\s+(.+)\s*$/
// Actions et tâches partagent la même cible (ActionTask).
// Préfixes acceptés : `*`, `-` (action courte) ou `>` (tâche structurée).
const LINE_ACTION = /^\s*[*\->]\s+(.+)\s*$/
const MENTION = /@([A-Za-zÀ-ÿ\-']+(?:\s+[A-Za-zÀ-ÿ\-']+)*)/

export function parseLines(lines: string[]): LocalParseResult {
  const decisions: ParsedDecision[] = []
  const orphans: ParsedAction[] = []
  const mentions = new Set<string>()
  let current: ParsedDecision | null = null
  let dOrder = 0
  let aOrder = 0

  for (const raw of lines) {
    if (!raw.trim()) continue

    let m = raw.match(LINE_DECISION)
    if (m) {
      dOrder++
      current = {
        title: m[1].trim(),
        raw_line: raw,
        order: dOrder,
        actions: [],
      }
      decisions.push(current)
      continue
    }

    m = raw.match(LINE_ACTION)
    if (m) {
      aOrder++
      let text = m[1].trim()
      const mention = text.match(MENTION)
      if (mention) {
        mentions.add(mention[1].trim())
        text = text.replace(MENTION, '').trim()
      }
      const action: ParsedAction = {
        title: text,
        raw_line: raw,
        mention: mention?.[1].trim() ?? null,
        order: aOrder,
      }
      if (current) current.actions.push(action)
      else orphans.push(action)
      continue
    }

    // Mention dans paragraphe libre
    const free = raw.match(MENTION)
    if (free) mentions.add(free[1].trim())
  }

  return { decisions, orphan_actions: orphans, mentions: Array.from(mentions) }
}

/**
 * Convertit un doc ProseMirror (Tiptap JSON) en liste de lignes texte avec
 * indentation par 4 espaces.
 */
export function tiptapToLines(doc: any): string[] {
  if (!doc) return []
  const lines: string[] = []
  const walk = (node: any, depth = 0, inBullet = false) => {
    if (!node) return
    const t = node.type
    const children = node.content ?? []

    if (t === 'paragraph' || t === 'heading') {
      const text = textOf(node)
      lines.push(' '.repeat(depth * 4) + (inBullet ? '* ' : '') + text)
      return
    }
    if (t === 'bulletList' || t === 'orderedList') {
      for (const c of children) walk(c, depth, true)
      return
    }
    if (t === 'listItem') {
      for (const c of children) walk(c, depth + (inBullet ? 1 : 0), true)
      return
    }
    if (t === 'doc') {
      for (const c of children) walk(c, 0, false)
      return
    }
    for (const c of children) walk(c, depth, inBullet)
  }

  walk(doc)
  return lines
}

function textOf(node: any): string {
  if (!node) return ''
  if (node.type === 'text') return node.text ?? ''
  return (node.content ?? []).map(textOf).join('')
}
