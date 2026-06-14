// Store Zustand pour piloter l'ouverture du sidebar IA depuis n'importe où.
// (Le bouton Briefing du Dashboard et tous les widgets contextuels peuvent
// envoyer un prompt initial.)
import { create } from 'zustand'

import type { AIContextScope } from './types'

interface AIChatState {
  isOpen: boolean
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
  consumeInitialPrompt: () => string | null
}

export const useAIChatStore = create<AIChatState>((set, get) => ({
  isOpen: false,
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
  consumeInitialPrompt: () => {
    const p = get().initialPrompt
    set({ initialPrompt: null })
    return p
  },
}))
