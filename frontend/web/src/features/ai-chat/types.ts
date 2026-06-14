// Types pour le chat IA MVP.

export type AIMessageRole = 'user' | 'assistant' | 'system' | 'tool'

export type AIContextScope = 'org' | 'meeting' | 'decision' | 'dashboard' | 'document'

export interface AIMessageCitations {
  loaders_used?: string[]
  action_request_ids?: string[]
  [k: string]: unknown
}

export type AIActionType =
  | 'create_decision_draft'
  | 'create_action_task'
  | 'create_action_plan'
  | 'assign_task'
  | 'update_task_status'
  | 'send_notification'

export type AIActionStatus = 'pending' | 'confirmed' | 'executed' | 'cancelled' | 'failed'

export interface AIActionRequest {
  id: string
  action_type: AIActionType
  summary: string
  payload: Record<string, unknown>
  status: AIActionStatus
  confirmed_at: string | null
  executed_at: string | null
  error_message: string
  result_object_type: string  // ex: "decisions.decision"
  result_object_id: string
  created_at: string
}

export interface AIMessage {
  id: string
  role: AIMessageRole
  content_md: string
  tokens: number
  created_at: string
  feedback: number | null
  citations_json?: AIMessageCitations
}

export interface AIConversation {
  id: string
  title: string
  context_scope: AIContextScope
  context_id: string
  is_archived: boolean
  created_at: string
  updated_at: string
  last_message_at: string
  message_count: number
}

export interface SendMessagePayload {
  message: string
  conversation_id?: string
  context_scope?: AIContextScope
  context_id?: string
  new_conversation_title?: string
}

export interface SendMessageResponse {
  conversation: AIConversation
  messages: AIMessage[]
  assistant_message: AIMessage
}

export interface ConversationMessagesResponse {
  conversation: AIConversation
  messages: AIMessage[]
}
