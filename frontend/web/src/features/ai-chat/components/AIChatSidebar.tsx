/**
 * AIChatSidebar — Assistant CODIR latéral, MVP.
 *
 * Caractéristiques :
 *   - Panneau fixe à droite, ouvert/fermé via le store Zustand
 *   - Contexte page injecté automatiquement (scope + id)
 *   - Historique de la conversation courante
 *   - Markdown basique pour les réponses (titres, listes, gras, code)
 *   - Suggestions contextuelles selon la page
 *   - Bouton "Nouvelle conversation" pour repartir de zéro
 *
 * Pas (encore) dans le MVP : streaming, tools, actions confirmées, RAG.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Bot, ChevronDown, ChevronUp, Loader2, Plus, Send, Sparkles,
  User, X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { cn } from '@/utils/cn'

import { aiChatApi, aiChatKeys } from '../api'
import { useAIChatStore } from '../store'
import type { AIContextScope, AIMessage } from '../types'

// ─── Suggestions contextuelles ─────────────────────────────

const SUGGESTIONS: Record<AIContextScope, string[]> = {
  org: [
    'Résume mon activité du jour',
    'Quelles tâches sont en retard ?',
    'Liste les décisions à valider',
    'Quels sont les sujets récurrents du CODIR ?',
  ],
  meeting: [
    'Résume cette réunion',
    'Extrait les décisions clés',
    'Identifie les actions à mener',
    'Prépare une note de synthèse pour la DG',
  ],
  decision: [
    'Reformule cette décision plus clairement',
    'Identifie les risques associés',
    'Propose un plan d\'action',
    'Suggère des échéances réalistes',
  ],
  dashboard: [
    'Prépare-moi le briefing du jour',
    'Quels sont les KPI à surveiller cette semaine ?',
    'Identifie les goulots d\'étranglement',
  ],
  document: [
    'Résume ce document',
    'Extrait les points clés',
    'Identifie les actions nécessaires',
  ],
}

// ─── Composant principal ───────────────────────────────────

export function AIChatSidebar() {
  const qc = useQueryClient()
  const isOpen = useAIChatStore((s) => s.isOpen)
  const close = useAIChatStore((s) => s.close)
  const activeConversationId = useAIChatStore((s) => s.activeConversationId)
  const setActiveConversation = useAIChatStore((s) => s.setActiveConversation)
  const contextScope = useAIChatStore((s) => s.contextScope)
  const contextId = useAIChatStore((s) => s.contextId)
  const consumeInitialPrompt = useAIChatStore((s) => s.consumeInitialPrompt)

  const [input, setInput] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  // ─── Récup historique conversation active ─────────────
  const { data: convData, isLoading: loadingMessages } = useQuery({
    queryKey: activeConversationId
      ? aiChatKeys.messages(activeConversationId)
      : ['ai-chat', 'messages', 'none'],
    queryFn: () => activeConversationId
      ? aiChatApi.getConversationMessages(activeConversationId)
      : Promise.resolve({ conversation: null as any, messages: [] }),
    enabled: !!activeConversationId && isOpen,
  })
  const messages: AIMessage[] = convData?.messages ?? []

  // ─── Liste des conversations (panneau "Historique") ───
  const { data: convList = [] } = useQuery({
    queryKey: aiChatKeys.conversations(),
    queryFn: () => aiChatApi.listConversations(),
    enabled: isOpen,
  })

  // ─── Send ─────────────────────────────────────────────
  const send = useMutation({
    mutationFn: (text: string) => aiChatApi.send({
      message: text,
      conversation_id: activeConversationId ?? undefined,
      context_scope: contextScope,
      context_id: contextId || undefined,
    }),
    onSuccess: (r) => {
      // Si nouvelle conv → on active la conv retournée
      if (!activeConversationId) {
        setActiveConversation(r.conversation.id)
      }
      qc.invalidateQueries({ queryKey: aiChatKeys.messages(r.conversation.id) })
      qc.invalidateQueries({ queryKey: aiChatKeys.conversations() })
      setInput('')
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail || e?.message || 'Erreur LLM'
      toast.error('Échec envoi message', { description: detail })
    },
  })

  // ─── Auto-scroll vers le bas + consume prompt initial ──
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, send.isPending, isOpen])

  useEffect(() => {
    if (!isOpen) return
    const initial = consumeInitialPrompt()
    if (initial && !send.isPending) {
      // Envoie automatiquement le prompt initial fourni à l'ouverture
      send.mutate(initial)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const t = input.trim()
    if (!t || send.isPending) return
    send.mutate(t)
  }

  function startNewConversation() {
    setActiveConversation(null)
    qc.invalidateQueries({ queryKey: aiChatKeys.conversations() })
  }

  function selectConversation(id: string) {
    setActiveConversation(id)
    setShowHistory(false)
  }

  const suggestions = SUGGESTIONS[contextScope] ?? SUGGESTIONS.org

  return (
    <>
      {/* ─── Backdrop mobile ─── */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={close}
          aria-hidden
        />
      )}

      {/* ─── Sidebar ─── */}
      <aside
        className={cn(
          'fixed top-0 right-0 h-screen w-full sm:w-[420px] z-50',
          'bg-bg-base border-l border-border',
          'flex flex-col shadow-2xl',
          'transition-transform duration-300 ease-out',
          isOpen ? 'translate-x-0' : 'translate-x-full',
        )}
        aria-hidden={!isOpen}
      >
        {/* Header */}
        <header className="flex items-center justify-between gap-3 px-5 py-4 border-b border-border bg-bg-subtle">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-copper-gradient grid place-items-center text-white shrink-0">
              <Bot size={16} />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold leading-tight">Assistant CODIR</div>
              <div className="text-2xs uppercase tracking-wider text-fg-muted">
                {contextScope === 'meeting' ? 'Contexte : Réunion'
                  : contextScope === 'decision' ? 'Contexte : Décision'
                  : contextScope === 'dashboard' ? 'Contexte : Cockpit'
                  : contextScope === 'document' ? 'Contexte : Document'
                  : 'Vue globale'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={() => setShowHistory((v) => !v)}
              className="p-1.5 rounded hover:bg-fg/10 text-fg-muted hover:text-fg"
              title="Historique des conversations"
            >
              {showHistory ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>
            <button
              type="button"
              onClick={startNewConversation}
              className="p-1.5 rounded hover:bg-fg/10 text-fg-muted hover:text-fg"
              title="Nouvelle conversation"
            >
              <Plus size={15} />
            </button>
            <button
              type="button"
              onClick={close}
              className="p-1.5 rounded hover:bg-fg/10 text-fg-muted hover:text-fg"
              aria-label="Fermer"
            >
              <X size={16} />
            </button>
          </div>
        </header>

        {/* Historique conversations (toggle) */}
        {showHistory && (
          <div className="border-b border-border bg-bg-subtle/50 p-3 max-h-48 overflow-auto">
            <div className="text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-2">
              Conversations récentes ({convList.length})
            </div>
            {convList.length === 0 ? (
              <p className="text-xs text-fg-subtle italic">Aucune conversation pour l'instant.</p>
            ) : (
              <ul className="space-y-1">
                {convList.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => selectConversation(c.id)}
                      className={cn(
                        'w-full text-left px-2.5 py-1.5 rounded text-xs hover:bg-fg/5 transition',
                        c.id === activeConversationId && 'bg-copper-500/10 text-copper-400',
                      )}
                    >
                      <div className="font-medium truncate">{c.title || 'Sans titre'}</div>
                      <div className="text-2xs text-fg-subtle">
                        {c.message_count} message{c.message_count > 1 ? 's' : ''}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-auto px-5 py-4 space-y-4">
          {!activeConversationId && messages.length === 0 && !send.isPending && (
            <EmptyConversation
              suggestions={suggestions}
              onPick={(s) => send.mutate(s)}
            />
          )}

          {loadingMessages && (
            <div className="flex items-center justify-center py-8 text-fg-muted">
              <Loader2 size={16} className="animate-spin" />
            </div>
          )}

          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}

          {send.isPending && (
            <div className="flex items-start gap-3 max-w-[90%]">
              <div className="w-7 h-7 rounded-full bg-copper-500/15 text-copper-400 grid place-items-center shrink-0">
                <Sparkles size={14} />
              </div>
              <div className="flex-1 bg-bg-elevated rounded-lg px-4 py-3 text-sm text-fg-muted flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" /> L'assistant réfléchit…
              </div>
            </div>
          )}
        </div>

        {/* Suggestions contextuelles si conversation vide */}
        {activeConversationId && messages.length === 0 && !send.isPending && (
          <div className="px-5 py-3 border-t border-border bg-bg-subtle/30">
            <div className="text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-2">
              Suggestions
            </div>
            <div className="flex flex-wrap gap-1.5">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send.mutate(s)}
                  className="text-xs px-2.5 py-1.5 rounded-md border border-border hover:border-copper-500/30 hover:bg-copper-500/5 text-fg-muted hover:text-fg"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <form
          onSubmit={handleSubmit}
          className="border-t border-border bg-bg-base p-3"
        >
          <div className="flex items-end gap-2">
            <textarea
              id="ai-chat-input"
              name="ai-chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e as any)
                }
              }}
              placeholder="Posez votre question…"
              rows={1}
              className="flex-1 resize-none px-3 py-2 rounded-lg bg-bg-elevated border border-border text-sm focus:border-copper-500/50 outline-none max-h-32"
              disabled={send.isPending}
            />
            <button
              type="submit"
              disabled={!input.trim() || send.isPending}
              className={cn(
                'p-2.5 rounded-lg transition shrink-0',
                input.trim() && !send.isPending
                  ? 'bg-copper-500 hover:bg-copper-600 text-white'
                  : 'bg-fg/10 text-fg-muted cursor-not-allowed',
              )}
              aria-label="Envoyer"
            >
              {send.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
            </button>
          </div>
          <p className="text-2xs text-fg-subtle mt-1.5 text-center">
            Entrée : envoyer · Maj+Entrée : nouvelle ligne · Bêta — les réponses peuvent être imparfaites
          </p>
        </form>
      </aside>
    </>
  )
}

// ─── Sous-composants ──────────────────────────────────────

function EmptyConversation({
  suggestions, onPick,
}: { suggestions: string[]; onPick: (s: string) => void }) {
  return (
    <div className="text-center py-8">
      <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-copper-gradient grid place-items-center text-white shadow-copper">
        <Sparkles size={22} />
      </div>
      <h3 className="serif text-h3 font-semibold mb-1.5">Bienvenue !</h3>
      <p className="text-sm text-fg-muted mb-5">
        Je suis l'Assistant CODIR. Comment puis-je vous aider ?
      </p>
      <div className="space-y-2">
        {suggestions.slice(0, 4).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="w-full text-left text-xs px-3 py-2.5 rounded-lg border border-border hover:border-copper-500/30 hover:bg-copper-500/5 text-fg-muted hover:text-fg transition"
          >
            <Sparkles size={11} className="inline mr-1.5 text-copper-400" />
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

// Labels FR des loaders backend pour affichage badge UI
const LOADER_LABELS: Record<string, string> = {
  my_tasks: 'Mes tâches',
  overdue_tasks: 'Tâches en retard',
  pending_decisions: 'Décisions à valider',
  upcoming_meetings: 'Réunions à venir',
  my_action_plans: 'Mes dossiers',
  baseline: 'Chiffres clés',
}

function MessageBubble({ message }: { message: AIMessage }) {
  const isUser = message.role === 'user'
  // Loaders utilisés (sauf "baseline" qui est toujours là, peu intéressant à afficher)
  const loaders = (message.citations_json?.loaders_used ?? [])
    .filter((l) => l !== 'baseline')

  return (
    <div className={cn(
      'flex items-start gap-3 max-w-[92%]',
      isUser ? 'ml-auto flex-row-reverse' : '',
    )}>
      <div className={cn(
        'w-7 h-7 rounded-full grid place-items-center shrink-0',
        isUser ? 'bg-fg/10 text-fg' : 'bg-copper-500/15 text-copper-400',
      )}>
        {isUser ? <User size={13} /> : <Sparkles size={13} />}
      </div>
      <div className={cn(
        'flex-1 rounded-lg px-4 py-3 text-sm leading-relaxed',
        isUser
          ? 'bg-copper-500/10 border border-copper-500/20'
          : 'bg-bg-elevated border border-border',
      )}>
        <SimpleMarkdown text={message.content_md} />

        {/* Badge "données utilisées" — transparence sur les sources */}
        {!isUser && loaders.length > 0 && (
          <div className="mt-2.5 pt-2.5 border-t border-border/50 flex items-center gap-1.5 flex-wrap">
            <span className="text-2xs uppercase tracking-wider text-fg-subtle font-semibold">
              📊 Données utilisées :
            </span>
            {loaders.map((l) => (
              <span
                key={l}
                className="text-2xs px-1.5 py-0.5 rounded bg-copper-500/10 text-copper-400 border border-copper-500/20"
                title={`Le backend a chargé "${LOADER_LABELS[l] ?? l}" pour répondre à votre question.`}
              >
                {LOADER_LABELS[l] ?? l}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Mini renderer Markdown pour les réponses IA.
 * Couvre les cas les plus fréquents (gras, italique, listes, blocs code, titres).
 * Pour du Markdown complet on switchera vers `react-markdown` plus tard.
 */
function SimpleMarkdown({ text }: { text: string }) {
  // Split en blocs (séparés par lignes vides)
  const blocks = text.split(/\n{2,}/)
  return (
    <div className="space-y-2.5">
      {blocks.map((block, i) => {
        const trimmed = block.trim()

        // Titre H3+
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={i} className="font-semibold text-sm">
              {inlineFmt(trimmed.slice(4))}
            </h4>
          )
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={i} className="font-semibold text-base text-copper-400">
              {inlineFmt(trimmed.slice(3))}
            </h3>
          )
        }
        if (trimmed.startsWith('# ')) {
          return (
            <h2 key={i} className="font-semibold text-lg text-copper-400">
              {inlineFmt(trimmed.slice(2))}
            </h2>
          )
        }

        // Liste à puces
        const bulletLines = trimmed.split('\n').filter(l => /^\s*[-*]\s/.test(l))
        if (bulletLines.length > 0 && bulletLines.length === trimmed.split('\n').length) {
          return (
            <ul key={i} className="list-disc list-inside space-y-1">
              {bulletLines.map((l, j) => (
                <li key={j}>{inlineFmt(l.replace(/^\s*[-*]\s+/, ''))}</li>
              ))}
            </ul>
          )
        }

        // Liste numérotée
        const numberedLines = trimmed.split('\n').filter(l => /^\s*\d+\.\s/.test(l))
        if (numberedLines.length > 0 && numberedLines.length === trimmed.split('\n').length) {
          return (
            <ol key={i} className="list-decimal list-inside space-y-1">
              {numberedLines.map((l, j) => (
                <li key={j}>{inlineFmt(l.replace(/^\s*\d+\.\s+/, ''))}</li>
              ))}
            </ol>
          )
        }

        // Bloc code (triple backtick)
        if (trimmed.startsWith('```') && trimmed.endsWith('```')) {
          const code = trimmed.replace(/^```\w*\n?/, '').replace(/\n?```$/, '')
          return (
            <pre key={i} className="bg-bg-base rounded p-3 overflow-x-auto text-xs font-mono">
              <code>{code}</code>
            </pre>
          )
        }

        // Paragraphe par défaut
        return <p key={i} className="whitespace-pre-wrap">{inlineFmt(trimmed)}</p>
      })}
    </div>
  )
}

/** Gras / italique / code inline. */
function inlineFmt(s: string): React.ReactNode {
  // Stratégie simple : on tokenize sur **...**, *...*, `...`
  const parts: React.ReactNode[] = []
  let remaining = s
  let key = 0
  const patterns = [
    { re: /^\*\*([^*]+)\*\*/, tag: 'strong' },
    { re: /^`([^`]+)`/,        tag: 'code' },
    { re: /^\*([^*]+)\*/,      tag: 'em' },
  ]
  while (remaining.length > 0) {
    let matched = false
    for (const p of patterns) {
      const m = remaining.match(p.re)
      if (m) {
        if (p.tag === 'strong') parts.push(<strong key={key++}>{m[1]}</strong>)
        else if (p.tag === 'em') parts.push(<em key={key++}>{m[1]}</em>)
        else if (p.tag === 'code')
          parts.push(
            <code key={key++} className="bg-bg-base px-1 py-0.5 rounded text-xs font-mono">
              {m[1]}
            </code>,
          )
        remaining = remaining.slice(m[0].length)
        matched = true
        break
      }
    }
    if (!matched) {
      // Avance d'1 char (en texte brut)
      // Optimisation : avale jusqu'au prochain marqueur ou fin
      const nextSpecial = remaining.search(/[*`]/)
      const chunk = nextSpecial < 0 ? remaining : remaining.slice(0, Math.max(1, nextSpecial))
      parts.push(chunk)
      remaining = remaining.slice(chunk.length)
    }
  }
  return <>{parts}</>
}
