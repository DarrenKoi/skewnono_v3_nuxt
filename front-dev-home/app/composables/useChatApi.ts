import { joinApiPath } from '~/utils/apiPath'

export interface ChatModel {
  id: string
  label: string
}

export interface ChatMessage {
  id: string
  thread_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  model?: string | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  latency_ms?: number | null
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

  const sendMessage = async (id: string, content: string): Promise<ChatMessage> =>
    (await $fetch<{ data: ChatMessage }>(url(`/chat/threads/${id}/messages`), {
      method: 'POST',
      body: { content }
    })).data

  return {
    fetchModels, fetchThreads, fetchThread,
    createThread, renameThread, deleteThread, sendMessage
  }
}
