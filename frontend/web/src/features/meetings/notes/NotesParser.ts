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
  due_date: string | null   // ISO yyyy-mm-dd
  priority: '' | 'low' | 'medium' | 'high' | 'critical'
  description_md: string
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

// Date d'échéance : 22/08/2026 — 22/08/26 — 22/08
const DUE_DATE = /\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b/

// Priorité : !low / !medium / !high / !critical (+ alias !l !m !h !c)
const PRIORITY = /!(low|medium|high|critical|l|m|h|c)\b/i
const PRIORITY_ALIASES: Record<string, ParsedAction['priority']> = {
  l: 'low', m: 'medium', h: 'high', c: 'critical',
  low: 'low', medium: 'medium', high: 'high', critical: 'critical',
}

function extractDueDate(text: string): { iso: string | null; rest: string } {
  const m = text.match(DUE_DATE)
  if (!m) return { iso: null, rest: text }
  const day = parseInt(m[1], 10)
  const month = parseInt(m[2], 10)
  const yearRaw = m[3]
  const today = new Date()
  let year = today.getFullYear()
  if (yearRaw) {
    year = parseInt(yearRaw, 10)
    if (year < 100) year += 2000
  }
  const dt = new Date(year, month - 1, day)
  if (
    isNaN(dt.getTime()) ||
    dt.getDate() !== day ||
    dt.getMonth() + 1 !== month
  ) {
    return { iso: null, rest: text }  // date invalide → ignorer
  }
  const iso = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  const cleaned = (text.slice(0, m.index!) + text.slice(m.index! + m[0].length))
    .replace(/\s{2,}/g, ' ')
    .trim()
  return { iso, rest: cleaned }
}

function extractPriority(text: string): { priority: ParsedAction['priority']; rest: string } {
  const m = text.match(PRIORITY)
  if (!m) return { priority: '', rest: text }
  const key = m[1].toLowerCase()
  const priority = PRIORITY_ALIASES[key] ?? ''
  const cleaned = (text.slice(0, m.index!) + text.slice(m.index! + m[0].length))
    .replace(/\s{2,}/g, ' ')
    .trim()
  return { priority, rest: cleaned }
}

export function parseLines(lines: string[]): LocalParseResult {
  const decisions: ParsedDecision[] = []
  const orphans: ParsedAction[] = []
  const mentions = new Set<string>()
  let current: ParsedDecision | null = null
  let currentAction: ParsedAction | null = null
  let dOrder = 0
  let aOrder = 0

  const flushAction = () => {
    if (currentAction && currentAction.description_md) {
      currentAction.description_md = currentAction.description_md.trim()
    }
    currentAction = null
  }

  for (const raw of lines) {
    if (!raw.trim()) { flushAction(); continue }

    let m = raw.match(LINE_DECISION)
    if (m) {
      flushAction()
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
      flushAction()
      aOrder++
      let text = m[1].trim()

      // Date + priorité d'abord (avant mention pour éviter collision)
      const due = extractDueDate(text)
      text = due.rest
      const prio = extractPriority(text)
      text = prio.rest

      const mention = text.match(MENTION)
      if (mention) {
        mentions.add(mention[1].trim())
        text = text.replace(MENTION, '').trim()
      }

      // Nettoyer les mots de liaison résiduels (d'ici / avant le / pour …)
      text = text
        .replace(/\b(d'ici|avant|jusqu'au|le|pour)\s*(le)?\s*$/i, '')
        .replace(/\s{2,}/g, ' ')
        .trim()

      currentAction = {
        title: text,
        raw_line: raw,
        mention: mention?.[1].trim() ?? null,
        order: aOrder,
        due_date: due.iso,
        priority: prio.priority,
        description_md: '',
      }
      if (current) current.actions.push(currentAction)
      else orphans.push(currentAction)
      continue
    }

    // Ligne indentée (≥2 espaces ou tab) après une action → description
    if (currentAction && (raw.startsWith('  ') || raw.startsWith('\t'))) {
      const indent = raw.replace(/^[\s\t]+/, '').trimEnd()
      if (indent) {
        currentAction.description_md = currentAction.description_md
          ? currentAction.description_md + '\n' + indent
          : indent
        continue
      }
    }

    flushAction()

    // Mention dans paragraphe libre
    const free = raw.match(MENTION)
    if (free) mentions.add(free[1].trim())
  }

  flushAction()
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
