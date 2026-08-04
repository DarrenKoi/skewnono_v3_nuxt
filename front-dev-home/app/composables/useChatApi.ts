import { joinApiPath } from '~/utils/apiPath'

export interface ChatModel {
  id: string
  label: string
  supports_tools: boolean
  supports_vision: boolean
}

export interface SourceRef {
  source_id: string
  source_type: 'manual' | 'meeting' | 'email' | 'report'
  title: string
  snippet: string
  revision: string | null
  occurred_at: string | null
  section: string | null
  page: number | null
  region: string | null
  locator: string | null
  score: number | null
}

export type FeedbackReason
  = | 'incorrect'
    | 'insufficient_evidence'
    | 'wrong_source'
    | 'outdated'
    | 'unclear'
    | 'incorrect_scope_rejection'
    | 'other'

export interface FeedbackInput {
  rating: 'up' | 'down'
  reasons: FeedbackReason[]
  comment: string | null
}

export interface MessageFeedback extends FeedbackInput {
  updated_at: string
}

export interface ChatMessage {
  id: string
  thread_id: string
  request_id: string | null
  role: 'user' | 'assistant' | 'system'
  content: string
  model?: string | null
  runtime: 'direct' | 'agent' | 'scope_rejection' | null
  scope_status: 'in_scope' | 'mixed' | 'out_of_scope' | 'unsafe' | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  latency_ms?: number | null
  sources: SourceRef[]
  feedback: MessageFeedback | null
  created_at: string
}

export interface ThreadSummary {
  id: string
  title: string
  model: string
  updated_at: string
}

export interface ThreadDetail extends ThreadSummary {
  user_id: string
  system_prompt?: string | null
  created_at: string
  messages: ChatMessage[]
}

export const useChatApi = () => {
  const config = useRuntimeConfig()
  const url = (p: string) => joinApiPath(config.public.apiBase, p)

  /**
   * Whether chat is in service on this deployment.
   *
   * One SPA bundle ships to every phase, so the page cannot tell production
   * from the office on its own — the backend is the only thing that knows.
   */
  const fetchAvailability = async (): Promise<boolean> =>
    (await $fetch<{ data: { available: boolean } }>(url('/chat/availability'))).data.available

  const fetchModels = async (): Promise<ChatModel[]> =>
    (await $fetch<{ data: ChatModel[] }>(url('/chat/models'))).data

  const fetchThreads = async (): Promise<ThreadSummary[]> =>
    (await $fetch<{ data: ThreadSummary[] }>(url('/chat/threads'))).data

  const fetchThread = async (id: string): Promise<ThreadDetail> =>
    (await $fetch<{ data: ThreadDetail }>(url(`/chat/threads/${id}`))).data

  const createThread = async (model: string, systemPrompt?: string): Promise<ThreadDetail> => {
    const t = (await $fetch<{ data: ThreadDetail }>(url('/chat/threads'), {
      method: 'POST',
      body: { model, system_prompt: systemPrompt || null }
    })).data
    return { ...t, messages: t.messages ?? [] }
  }

  const renameThread = async (id: string, title: string): Promise<void> => {
    await $fetch(url(`/chat/threads/${id}`), { method: 'PATCH', body: { title } })
  }

  const deleteThread = async (id: string): Promise<void> => {
    await $fetch(url(`/chat/threads/${id}`), { method: 'DELETE' })
  }

  const sendMessage = async (
    id: string,
    content: string,
    requestId: string
  ): Promise<ChatMessage> =>
    (await $fetch<{ data: ChatMessage }>(url(`/chat/threads/${id}/messages`), {
      method: 'POST',
      body: { content, request_id: requestId }
    })).data

  const putFeedback = async (
    messageId: string,
    feedback: FeedbackInput
  ): Promise<MessageFeedback> =>
    (await $fetch<{ data: MessageFeedback }>(url(`/chat/messages/${messageId}/feedback`), {
      method: 'PUT',
      body: feedback
    })).data

  const deleteFeedback = async (messageId: string): Promise<void> => {
    await $fetch(url(`/chat/messages/${messageId}/feedback`), { method: 'DELETE' })
  }

  return {
    fetchAvailability,
    fetchModels, fetchThreads, fetchThread,
    createThread, renameThread, deleteThread, sendMessage,
    putFeedback, deleteFeedback
  }
}
