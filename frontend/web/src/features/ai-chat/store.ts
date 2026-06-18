// Store Zustand pour piloter l'ouverture du sidebar IA depuis n'importe où.
// (Le bouton Briefing du Dashboard et tous les widgets contextuels peuvent
// envoyer un prompt initial.)
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type { AIContextScope } from './types'

/**
 * Tailles du panel chat IA.
 *   - narrow   : 420px — chat compact, ne couvre pas le contenu principal
 *   - wide     : 720px — meilleure lecture des tableaux et longs paragraphes
 *   - fullpage : ~80vw — utile sur grand écran pour des synthèses détaillées
 *
 * Sur mobile (lg-down) on force toujours w-full peu importe la préférence.
 */
export type AIChatSize = 'narrow' | 'wide' | 'fullpage'

interface AIChatState {
  isOpen: boolean
  size: AIChatSize  // ⚙ persisté en localStorage
  // Conversation active (null = en démarre une nouvelle au prochain send)
  activeConversationId: string | null
  // Contexte courant injecté dans chaque message envoyé
  contextScope: AIContextScope
  contextId: string
  // Prompt à pré-remplir dans l'input quand on ouvre le sidebar
  initialPrompt: string | null

  open: (opts?: {
    contextScope?: AIContextScope
    contextId?: string
    initialPrompt?: string
    conversationId?: string
  }) => void
  close: () => void
  toggle: () => void
  setActiveConversation: (id: string | null) => void
  setContext: (scope: AIContextScope, id?: string) => void
  setSize: (size: AIChatSize) => void
  cycleSize: () => void
  consumeInitialPrompt: () => string | null
  // Multi-org : appelé au switch d'organisation. Reset toute la session de chat
  // car les conversations + objets de l'ancienne org n'appartiennent plus à la
  // nouvelle (sinon 404 sur les requêtes). Garde uniquement les préférences.
  resetForOrgSwitch: () => void
}

const SIZE_ORDER: AIChatSize[] = ['narrow', 'wide', 'fullpage']

export const useAIChatStore = create<AIChatState>()(
  persist(
    (set, get) => ({
      isOpen: false,
      size: 'narrow',
      activeConversationId: null,
      contextScope: 'org',
      contextId: '',
      initialPrompt: null,

      open: (opts) => set({
        isOpen: true,
        contextScope: opts?.contextScope ?? get().contextScope,
        contextId: opts?.contextId ?? get().contextId,
        initialPrompt: opts?.initialPrompt ?? null,
        activeConversationId: opts?.conversationId ?? get().activeConversationId,
      }),
      close: () => set({ isOpen: false }),
      toggle: () => set({ isOpen: !get().isOpen }),
      setActiveConversation: (id) => set({ activeConversationId: id }),
      setContext: (scope, id = '') => set({ contextScope: scope, contextId: id }),
      setSize: (size) => set({ size }),
      cycleSize: () => {
        const current = get().size
        const idx = SIZE_ORDER.indexOf(current)
        const next = SIZE_ORDER[(idx + 1) % SIZE_ORDER.length]
        set({ size: next })
      },
      consumeInitialPrompt: () => {
        const p = get().initialPrompt
        set({ initialPrompt: null })
        return p
      },
      resetForOrgSwitch: () => set({
        isOpen: false,
        activeConversationId: null,
        contextScope: 'org',
        contextId: '',
        initialPrompt: null,
        // `size` (préférence UI) est conservée
      }),
    }),
    {
      name: 'codir-ai-chat',
      // On ne persiste QUE la taille (préférence utilisateur).
      // L'état d'ouverture, la conversation active et le contexte sont volatils.
      partialize: (s) => ({ size: s.size }) as any,
    },
  ),
)
