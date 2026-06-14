// API client pour le chat IA.
import { apiClient } from '@/api/client'

import type {
  AIConversation, ConversationMessagesResponse,
  SendMessagePayload, SendMessageResponse,
} from './types'

export const aiChatApi = {
  send: async (payload: SendMessagePayload) =>
    (await apiClient.post<SendMessageResponse>('/ai-chat/send/', payload, {
      timeout: 60_000,  // LLM peut prendre ~30s parfois
    })).data,

  listConversations: async () =>
    (await apiClient.get<{ results: AIConversation[] }>('/ai-chat/conversations/')).data.results,

  getConversationMessages: async (id: string) =>
    (await apiClient.get<ConversationMessagesResponse>(
      `/ai-chat/conversations/${id}/messages/`,
    )).data,

  archive: async (id: string) =>
    (await apiClient.post<AIConversation>(`/ai-chat/conversations/${id}/archive/`)).data,
}

export const aiChatKeys = {
  all: ['ai-chat'] as const,
  conversations: () => [...aiChatKeys.all, 'conversations'] as const,
  messages: (id: string) => [...aiChatKeys.all, 'messages', id] as const,
}
