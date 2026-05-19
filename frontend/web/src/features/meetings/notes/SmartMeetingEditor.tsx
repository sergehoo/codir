/**
 * SmartMeetingEditor — éditeur Tiptap style Notion/Linear.
 *
 * Features :
 *  - Lignes commençant par `# ` → décorées comme « DÉCISION » (badge orange).
 *  - Lignes de liste à puces avec `* ` → décorées « ACTION ».
 *  - Mentions `@…` avec popup d'autocomplete sur les membres de la réunion.
 *  - Autosave debounced (1.2 s) avec indicateur live.
 *  - Plain-text fallback exporté en parallèle pour la persistance.
 */
import { Mention } from '@tiptap/extension-mention'
import { Placeholder } from '@tiptap/extension-placeholder'
import { EditorContent, ReactRenderer, useEditor } from '@tiptap/react'
import { StarterKit } from '@tiptap/starter-kit'
import { Decoration, DecorationSet } from '@tiptap/pm/view'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Extension } from '@tiptap/core'
import { useEffect, useRef, useState } from 'react'

import { meetingsApi } from '../api'
import { DatePickerPopup } from './DatePickerPopup'
import { MentionAutocomplete } from './MentionAutocomplete'
import { tiptapToLines } from './NotesParser'

// ─── Décoration live des lignes # / * / > ─────────────────────
// Patterns assouplis : on décore dès que la ligne COMMENCE par le marqueur.
// L'espace après n'est plus obligatoire — du coup le badge s'affiche au tout
// premier keystroke.
//   #  → DÉCISION   (titre en gras + souligné — l'identifiant du plan d'action)
//   *  → ACTION     (item rapide à mener en séance)
//   >  → TÂCHE      (tâche structurée — rattachée au plan parent)
const DECISION_RE = /^\s*#(?:\s|$)/      // # ou # texte
const ACTION_RE   = /^\s*[*-](?:\s|$)/   // * ou - texte
const TASK_RE     = /^\s*>(?:\s|$)/      // > ou > texte

// Décorations inline (s'appliquent aux substrings dans le texte) : date,
// priorité — affichent un symbole + couleur sans toucher au contenu.
const INLINE_DATE_RE     = /\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b/g
const INLINE_PRIORITY_RE = /!(low|medium|high|critical|l|m|h|c)\b/gi

const SmartLineDecoration = Extension.create({
  name: 'smartLineDecoration',
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('smartLineDecoration'),
        props: {
          decorations(state) {
            const decos: Decoration[] = []
            state.doc.descendants((node, pos) => {
              // ── Décoration de ligne (textblock) ──
              if (node.isTextblock) {
                const text = node.textContent
                if (DECISION_RE.test(text)) {
                  decos.push(
                    Decoration.node(pos, pos + node.nodeSize, {
                      class: 'smart-line smart-line-decision',
                    }),
                  )
                } else if (TASK_RE.test(text)) {
                  decos.push(
                    Decoration.node(pos, pos + node.nodeSize, {
                      class: 'smart-line smart-line-task',
                    }),
                  )
                } else if (ACTION_RE.test(text)) {
                  decos.push(
                    Decoration.node(pos, pos + node.nodeSize, {
                      class: 'smart-line smart-line-action',
                    }),
                  )
                }
              }
              // ── Décorations inline (sur les text nodes) ──
              if (node.isText && node.text) {
                const text = node.text
                // Dates DD/MM[/YY[YY]]
                INLINE_DATE_RE.lastIndex = 0
                let m: RegExpExecArray | null
                while ((m = INLINE_DATE_RE.exec(text)) !== null) {
                  decos.push(
                    Decoration.inline(
                      pos + m.index,
                      pos + m.index + m[0].length,
                      { class: 'smart-inline-date' },
                    ),
                  )
                }
                // Priorités !low/!medium/!high/!critical (+ alias 1 lettre)
                INLINE_PRIORITY_RE.lastIndex = 0
                while ((m = INLINE_PRIORITY_RE.exec(text)) !== null) {
                  const key = m[1].toLowerCase().charAt(0) // l|m|h|c
                  decos.push(
                    Decoration.inline(
                      pos + m.index,
                      pos + m.index + m[0].length,
                      { class: `smart-inline-priority smart-inline-priority-${key}` },
                    ),
                  )
                }
              }
            })
            return DecorationSet.create(state.doc, decos)
          },
        },
      }),
    ]
  },
})

// ─── Tabulation : indenter dans une liste, sinon insérer un Tab caractère ──
const TabHandler = Extension.create({
  name: 'tabHandler',
  addKeyboardShortcuts() {
    return {
      Tab: ({ editor }) => {
        // Si on est dans une liste → enfoncer un niveau (sinkListItem)
        if (editor.can().sinkListItem('listItem')) {
          return editor.chain().focus().sinkListItem('listItem').run()
        }
        // Sinon : insérer un caractère tab (\t)
        return editor.chain().focus().insertContent('\t').run()
      },
      'Shift-Tab': ({ editor }) => {
        // Sortir d'un niveau de liste
        if (editor.can().liftListItem('listItem')) {
          return editor.chain().focus().liftListItem('listItem').run()
        }
        return false
      },
    }
  },
})

// ─── Datepicker : Cmd+D / Ctrl+D ouvre le sélecteur de date ──────
function buildDatePickerExtension(open: () => void) {
  return Extension.create({
    name: 'datepickerShortcut',
    addKeyboardShortcuts() {
      return {
        'Mod-d': () => { open(); return true },
        'Mod-D': () => { open(); return true },
      }
    },
  })
}

// ─── Mention factory ──────────────────────────────────────────

function buildMentionExtension(meetingId: string) {
  return Mention.configure({
    HTMLAttributes: { class: 'smart-mention' },
    // Rendu HTML : on n'inclut PAS le `@` dans le contenu, c'est le CSS
    // (`.smart-mention::before { content: '@' }`) qui le préfixe visuellement.
    // Sans cet override, on a `@@Catherine` car Tiptap met `@` dans le HTML
    // ET le CSS rajoute le sien — d'où le doublon.
    renderHTML({ options, node }) {
      return [
        'span',
        {
          ...options.HTMLAttributes,
          'data-id': node.attrs.id,
          'data-label': node.attrs.label,
        },
        `${node.attrs.label ?? node.attrs.id}`,
      ]
    },
    // Texte plain (export, copier-coller, parser backend) : on garde le `@`.
    renderText({ node }) {
      return `@${node.attrs.label ?? node.attrs.id}`
    },
    suggestion: {
      char: '@',
      items: async ({ query }: { query: string }) => {
        try {
          const list = await meetingsApi.mentionCandidates(meetingId, query)
          return list
        } catch {
          return []
        }
      },
      render: () => {
        let component: ReactRenderer<any> | null = null
        let popup: HTMLElement | null = null

        return {
          onStart: (props: any) => {
            component = new ReactRenderer(MentionAutocomplete, {
              props, editor: props.editor,
            })
            popup = document.createElement('div')
            popup.className = 'smart-mention-popup'
            popup.appendChild(component.element)
            document.body.appendChild(popup)
            updatePopupPosition(popup, props.clientRect?.())
          },
          onUpdate(props: any) {
            component?.updateProps(props)
            if (popup) updatePopupPosition(popup, props.clientRect?.())
          },
          onKeyDown(props: any) {
            if (props.event.key === 'Escape') {
              popup?.remove()
              return true
            }
            return (component?.ref as any)?.onKeyDown?.(props.event) ?? false
          },
          onExit() {
            popup?.remove()
            component?.destroy()
          },
        }
      },
    },
  })
}

function updatePopupPosition(el: HTMLElement, rect?: DOMRect | null) {
  if (!rect) return
  el.style.position = 'fixed'
  el.style.top = `${rect.bottom + 6}px`
  el.style.left = `${rect.left}px`
  el.style.zIndex = '9999'
}

// ─── Composant principal ──────────────────────────────────────

export function SmartMeetingEditor({
  meetingId,
  initialJson,
  onChange,
  onAutosave,
  saving,
  readOnly = false,
}: {
  meetingId: string
  initialJson: any
  onChange: (json: any, plain: string) => void
  onAutosave: () => void
  saving: 'idle' | 'saving' | 'saved' | 'error'
  readOnly?: boolean
}) {
  const debounceRef = useRef<number | null>(null)
  const [dateOpen, setDateOpen] = useState(false)
  const [dateAnchor, setDateAnchor] = useState<{ top: number; left: number } | null>(null)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder:
          "Prenez vos notes…\n\nAstuce :\n  # Décision   — la ligne devient une décision\n  * Action      — item rapide à mener\n  > Tâche       — tâche structurée (date 22/08/2026, !high, @Nom)\n  @Prénom      — mentionner un membre\n\n  ⌘D ouvre un sélecteur de date — 2 espaces sous la tâche = description",
      }),
      buildMentionExtension(meetingId),
      SmartLineDecoration,
      TabHandler,
      buildDatePickerExtension(() => {
        // Capture la position du curseur pour ancrer le popup
        const sel = window.getSelection()
        if (sel && sel.rangeCount > 0) {
          const r = sel.getRangeAt(0).getBoundingClientRect()
          if (r.top || r.left) {
            setDateAnchor({ top: r.bottom + 6, left: r.left })
          } else {
            setDateAnchor(null)
          }
        }
        setDateOpen(true)
      }),
    ],
    content: initialJson ?? '',
    editable: !readOnly,
    autofocus: 'end',
    onUpdate({ editor }) {
      const json = editor.getJSON()
      // Plain export *avec* marqueurs `* ` pour que le parser backend détecte les actions
      const plain = tiptapToLines(json).join('\n')
      onChange(json, plain)
      // debounce 1.2s
      if (debounceRef.current) window.clearTimeout(debounceRef.current)
      debounceRef.current = window.setTimeout(() => {
        onAutosave()
      }, 1200)
    },
  })

  // Synchronise quand initialJson change (chargement initial uniquement)
  useEffect(() => {
    if (editor && initialJson && Object.keys(initialJson).length > 0) {
      const current = editor.getJSON()
      if (JSON.stringify(current) === '{"type":"doc","content":[{"type":"paragraph"}]}') {
        editor.commands.setContent(initialJson, false)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialJson, editor])

  if (!editor) return null

  return (
    <div className="smart-editor relative">
      <EditorContent editor={editor} className="prose prose-sm max-w-none focus:outline-none" />
      <SaveBadge state={saving} />
      <DatePickerPopup
        open={dateOpen}
        anchor={dateAnchor}
        onClose={() => setDateOpen(false)}
        onSelect={(formatted) => {
          // Insère " DD/MM/YYYY" au curseur (espace avant pour ne pas coller au mot)
          const cur = editor.state.doc.textBetween(
            Math.max(0, editor.state.selection.from - 1),
            editor.state.selection.from,
          )
          const prefix = cur && cur !== ' ' && cur !== '\n' ? ' ' : ''
          editor.chain().focus().insertContent(`${prefix}${formatted}`).run()
          setDateOpen(false)
        }}
      />
    </div>
  )
}

function SaveBadge({ state }: { state: 'idle' | 'saving' | 'saved' | 'error' }) {
  const map = {
    idle:   { dot: 'bg-fg-subtle',   label: '' },
    saving: { dot: 'bg-warning animate-pulse', label: 'Enregistrement…' },
    saved:  { dot: 'bg-success', label: 'Enregistré' },
    error:  { dot: 'bg-danger',  label: 'Erreur' },
  }[state]
  if (!map.label) return null
  return (
    <div className="fixed bottom-4 right-6 z-30 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-elevated/90 backdrop-blur border border-border text-2xs uppercase tracking-wider text-fg-muted shadow-lg">
      <span className={`w-1.5 h-1.5 rounded-full ${map.dot}`} />
      {map.label}
    </div>
  )
}
