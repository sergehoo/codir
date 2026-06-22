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
  Bot, Check, ChevronDown, ChevronUp, Copy, FileText, Loader2,
  ListTodo, Maximize2, Minimize2, Plus, Send, Sparkles, User, X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { cn } from '@/utils/cn'

import { aiChatApi, aiChatKeys } from '../api'
import { useAIChatStore } from '../store'
import type { AIContextScope, AIMessage } from '../types'

import { AIActionConfirmationCard } from './AIActionConfirmationCard'

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

// Tailwind classes par taille — utilisé par className du <aside>
// Sur mobile (< sm) on garde toujours w-full peu importe la préférence.
const SIZE_CLASSES = {
  narrow:   'w-full sm:w-[420px]',
  wide:     'w-full sm:w-[640px] lg:w-[720px]',
  fullpage: 'w-full sm:w-[80vw] sm:max-w-[1200px]',
} as const

export function AIChatSidebar() {
  const qc = useQueryClient()
  const isOpen = useAIChatStore((s) => s.isOpen)
  const close = useAIChatStore((s) => s.close)
  const size = useAIChatStore((s) => s.size)
  const cycleSize = useAIChatStore((s) => s.cycleSize)
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
    // Lot 2 — Agent proactif : à l'ouverture du sidebar, on considère que
    // les alertes proactives ont été vues → marque comme lues + raffraîchit
    // le compteur pour faire disparaître le badge.
    aiChatApi.proactiveMarkRead()
      .then(() => qc.invalidateQueries({ queryKey: aiChatKeys.proactiveCount() }))
      .catch(() => {/* non-bloquant */})
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
          'fixed top-0 right-0 h-screen z-50',
          SIZE_CLASSES[size],
          'bg-bg-base border-l border-border',
          'flex flex-col shadow-2xl',
          'transition-[transform,width] duration-300 ease-out',
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
            {/* ⤢ Resize — cycle narrow → wide → fullpage → narrow */}
            <button
              type="button"
              onClick={cycleSize}
              className="p-1.5 rounded hover:bg-fg/10 text-fg-muted hover:text-fg hidden sm:inline-flex"
              title={
                size === 'narrow'   ? 'Agrandir (mode large)'
                : size === 'wide'   ? 'Agrandir au maximum (pleine page)'
                                    : 'Réduire (mode compact)'
              }
              aria-label="Changer la taille du panneau"
            >
              {size === 'fullpage'
                ? <Minimize2 size={14} />
                : <Maximize2 size={14} />}
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
            <MessageBubble key={m.id} message={m} conversationId={activeConversationId} />
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

function MessageBubble({
  message, conversationId,
}: { message: AIMessage; conversationId: string | null }) {
  const isUser = message.role === 'user'
  // Loaders utilisés (sauf "baseline" qui est toujours là, peu intéressant à afficher)
  const loaders = (message.citations_json?.loaders_used ?? [])
    .filter((l) => l !== 'baseline')
  const actionIds = (message.citations_json?.action_request_ids ?? []) as string[]

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

        {/* Cartes d'action proposées par l'IA */}
        {!isUser && actionIds.length > 0 && conversationId && (
          <div className="mt-2 -mx-1">
            {actionIds.map((id) => (
              <AIActionConfirmationCard
                key={id}
                actionId={id}
                conversationId={conversationId}
              />
            ))}
          </div>
        )}

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

        {/* Actions sur la réponse — uniquement messages assistant */}
        {!isUser && <AIResponseActions message={message} />}
      </div>
    </div>
  )
}

function AIResponseActions({ message }: { message: AIMessage }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    try {
      navigator.clipboard.writeText(message.content_md)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Impossible de copier — votre navigateur bloque l\'accès au presse-papier.')
    }
  }

  function handleInsertInMeeting() {
    // Phase 4 : intégration avec un éditeur de CR de réunion ouvert.
    // Pour l'instant : copie dans le presse-papier + toast informatif.
    try {
      navigator.clipboard.writeText(message.content_md)
      toast.success('Réponse copiée — collez-la dans le compte rendu.', {
        description: 'L\'insertion directe dans l\'éditeur de CR arrive bientôt.',
        duration: 5000,
      })
    } catch {
      toast.error('Copie impossible.')
    }
  }

  function handleConvertToTask() {
    // Phase 3 (actions confirmées) : enverra cette réponse au backend pour
    // proposer la création d'une tâche. Pour l'instant : placeholder.
    toast.info('Création de tâche depuis le chat', {
      description: 'Pour proposer une vraie tâche, demande à l\'assistant : « Crée une tâche pour [Nom] : [titre] avant [date] ». Il te proposera une carte de confirmation.',
      duration: 8000,
    })
  }

  return (
    <div className="mt-2 pt-2 border-t border-border/40 flex items-center gap-1 flex-wrap text-2xs">
      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-fg/10 text-fg-muted hover:text-fg transition"
        title="Copier la réponse dans le presse-papier"
      >
        {copied
          ? <><Check size={11} className="text-success" /> Copié</>
          : <><Copy size={11} /> Copier</>}
      </button>
      <button
        type="button"
        onClick={handleInsertInMeeting}
        className="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-fg/10 text-fg-muted hover:text-fg transition"
        title="Insérer dans le compte rendu d'une réunion"
      >
        <FileText size={11} /> Insérer dans un CR
      </button>
      <button
        type="button"
        onClick={handleConvertToTask}
        className="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-fg/10 text-fg-muted hover:text-fg transition"
        title="Créer une tâche à partir de cette réponse"
      >
        <ListTodo size={11} /> En faire une tâche
      </button>
    </div>
  )
}

/**
 * Renderer Markdown enrichi pour les réponses IA.
 *
 * Supporte :
 *   - Titres (# / ## / ### / ####)
 *   - Listes à puces et numérotées
 *   - Tableaux (syntaxe pipe Markdown standard)
 *   - Gras / italique / code inline
 *   - Blocs code triple backtick
 *   - Blocs custom :::alert / :::decision / :::action / :::risk / :::quote
 *   - Citations Markdown standard (lignes commençant par >)
 *   - Séparateurs (---)
 */
function SimpleMarkdown({ text }: { text: string }) {
  // Split en blocs (séparés par lignes vides)
  const blocks = text.split(/\n{2,}/)
  return (
    <div className="space-y-2.5">
      {blocks.map((block, i) => <Block key={i} text={block.trim()} />)}
    </div>
  )
}

function Block({ text }: { text: string }) {
  if (!text) return null

  // Séparateur
  if (/^-{3,}$/.test(text)) {
    return <hr className="border-border my-2" />
  }

  // Titres
  if (text.startsWith('#### ')) {
    return <h5 className="font-semibold text-xs uppercase tracking-wider text-fg-muted">{inlineFmt(text.slice(5))}</h5>
  }
  if (text.startsWith('### ')) {
    return <h4 className="font-semibold text-sm">{inlineFmt(text.slice(4))}</h4>
  }
  if (text.startsWith('## ')) {
    return <h3 className="font-semibold text-base text-copper-400">{inlineFmt(text.slice(3))}</h3>
  }
  if (text.startsWith('# ')) {
    return <h2 className="font-semibold text-lg text-copper-400">{inlineFmt(text.slice(2))}</h2>
  }

  // Blocs custom :::type ... :::
  const customMatch = text.match(/^:::(\w+)\s*\n?([\s\S]*?)\n?:::\s*$/)
  if (customMatch) {
    return <CustomBlock type={customMatch[1].toLowerCase()} content={customMatch[2]} />
  }

  // Tableau (au moins 2 lignes avec des | + une ligne de séparation avec --- )
  if (text.includes('|') && /\n\s*\|?[\s:|-]+\|/.test(text)) {
    const table = parseMarkdownTable(text)
    if (table) return <MarkdownTable {...table} />
  }

  // Bloc code triple backtick
  if (text.startsWith('```') && text.endsWith('```')) {
    const code = text.replace(/^```\w*\n?/, '').replace(/\n?```$/, '')
    return (
      <pre className="bg-bg-base rounded p-3 overflow-x-auto text-xs font-mono">
        <code>{code}</code>
      </pre>
    )
  }

  // Citation Markdown
  if (text.split('\n').every(l => l.startsWith('>'))) {
    return (
      <blockquote className="border-l-2 border-copper-500/40 pl-3 italic text-fg-muted">
        {inlineFmt(text.replace(/^> ?/gm, ''))}
      </blockquote>
    )
  }

  // Liste à puces
  const lines = text.split('\n')
  const allBullets = lines.every(l => /^\s*[-*]\s/.test(l)) && lines.length > 0
  if (allBullets) {
    return (
      <ul className="list-disc list-inside space-y-1">
        {lines.map((l, j) => (
          <li key={j}>{inlineFmt(l.replace(/^\s*[-*]\s+/, ''))}</li>
        ))}
      </ul>
    )
  }

  // Liste numérotée
  const allNumbered = lines.every(l => /^\s*\d+\.\s/.test(l)) && lines.length > 0
  if (allNumbered) {
    return (
      <ol className="list-decimal list-inside space-y-1">
        {lines.map((l, j) => (
          <li key={j}>{inlineFmt(l.replace(/^\s*\d+\.\s+/, ''))}</li>
        ))}
      </ol>
    )
  }

  // Paragraphe par défaut
  return <p className="whitespace-pre-wrap">{inlineFmt(text)}</p>
}

// ─── Blocs custom :::type ─────────────────────────────────────

function CustomBlock({ type, content }: { type: string; content: string }) {
  const PRESETS: Record<string, { bg: string; border: string; icon: string; label: string }> = {
    alert:    { bg: 'bg-amber-500/10',  border: 'border-amber-500/40',  icon: '⚠',  label: 'Alerte' },
    warning:  { bg: 'bg-amber-500/10',  border: 'border-amber-500/40',  icon: '⚠',  label: 'Attention' },
    danger:   { bg: 'bg-red-500/10',    border: 'border-red-500/40',    icon: '🔴', label: 'Critique' },
    decision: { bg: 'bg-copper-500/10', border: 'border-copper-500/40', icon: '✓',  label: 'Décision proposée' },
    action:   { bg: 'bg-blue-500/10',   border: 'border-blue-500/40',   icon: '→',  label: 'Action recommandée' },
    risk:     { bg: 'bg-orange-500/10', border: 'border-orange-500/40', icon: '⚡', label: 'Risque identifié' },
    quote:    { bg: 'bg-fg/5',          border: 'border-fg/20',         icon: '"',  label: 'Citation' },
    info:     { bg: 'bg-blue-500/10',   border: 'border-blue-500/40',   icon: 'ℹ',  label: 'Information' },
    success:  { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', icon: '✓', label: 'Succès' },
  }
  const preset = PRESETS[type] ?? PRESETS.info
  return (
    <div className={cn('rounded-lg border p-3 my-2', preset.bg, preset.border)}>
      <div className="flex items-center gap-2 text-2xs uppercase tracking-widest font-semibold mb-1.5 text-fg-muted">
        <span className="text-sm">{preset.icon}</span> {preset.label}
      </div>
      <div className="text-sm space-y-1.5">
        {content.split(/\n{2,}/).map((sub, i) => <Block key={i} text={sub.trim()} />)}
      </div>
    </div>
  )
}

// ─── Tableau Markdown ─────────────────────────────────────────

function parseMarkdownTable(text: string): { headers: string[]; rows: string[][] } | null {
  const lines = text.split('\n').filter(l => l.trim())
  if (lines.length < 2) return null
  // Trouve la ligne de séparation (---|---)
  const sepIdx = lines.findIndex(l => /^\|?[\s:|-]+\|/.test(l) && l.includes('-'))
  if (sepIdx < 1) return null

  const headerLine = lines[sepIdx - 1]
  const headers = headerLine
    .replace(/^\||\|$/g, '')
    .split('|')
    .map(c => c.trim())

  const rows: string[][] = []
  for (let i = sepIdx + 1; i < lines.length; i++) {
    const cells = lines[i]
      .replace(/^\||\|$/g, '')
      .split('|')
      .map(c => c.trim())
    if (cells.length > 0) rows.push(cells)
  }

  if (headers.length === 0 || rows.length === 0) return null
  return { headers, rows }
}

function MarkdownTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border my-2">
      <table className="w-full text-xs">
        <thead className="bg-bg-subtle">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="text-left px-3 py-2 font-semibold uppercase tracking-wider text-2xs">
                {inlineFmt(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row, ri) => (
            <tr key={ri} className="hover:bg-fg/5">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 align-top">
                  {inlineFmt(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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
