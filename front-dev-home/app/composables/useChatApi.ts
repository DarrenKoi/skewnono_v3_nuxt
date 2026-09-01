import { joinApiPath } from '~/utils/apiPath'

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
  /**
   * Opaque figure token, never a storage key — the server owns the directory,
   * bucket, prefix and `.webp` extension. `null` for text and table evidence,
   * which is the common case. Resolve it with `figureUrl` from
   * `~/utils/chatSources`.
   */
  figure_id: string | null
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
  /**
   * The turn's lifecycle, on the assistant row. A turn is reserved as
   * `pending` when the question is sent and settles to `done` or `failed`;
   * the page polls the thread until it leaves `pending`. Separate from
   * `runtime`, which says what answered rather than whether it finished.
   * For an assistant row `created_at` is when the turn STARTED, which is what
   * the elapsed-seconds display counts from.
   */
  status: 'pending' | 'done' | 'failed'
  /**
   * Set only on a failed turn, and drawn from the same vocabulary the API
   * puts in an error body — one mapping whether the failure arrived on the
   * POST or through a poll.
   */
  error_code: 'runtime_denied' | 'runtime_unavailable' | 'gateway_timeout' | null
  error_message: string | null
  /** What answered, when the RAG reports it. It usually does not. */
  model?: string | null
  runtime: 'rag' | 'scope_rejection' | null
  scope_status: 'in_scope' | 'mixed' | 'out_of_scope' | 'unsafe' | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  latency_ms?: number | null
  sources: SourceRef[]
  feedback: MessageFeedback | null
  /**
   * Agent mode only, on the assistant turn: the retrieval expansion of the
   * question (acronyms spelled out, Korean/English paired) — `null` when the
   * runtime was direct, the scope was rejected, or nothing changed — and the
   * RAG's suggested next questions (empty outside agent mode).
   */
  rewrite: string | null
  follow_ups: string[]
  created_at: string
}

export interface ThreadSummary {
  id: string
  title: string
  updated_at: string
}

export interface ThreadDetail extends ThreadSummary {
  user_id: string
  created_at: string
  messages: ChatMessage[]
}

export const useChatApi = () => {
  const config = useRuntimeConfig()
  const url = (p: string) => joinApiPath(config.public.apiBase, p)

  /**
   * Whether chat is in service here, and how long one turn may take.
   *
   * One SPA bundle ships to every phase, so the page cannot tell production
   * from the office on its own — the backend is the only thing that knows.
   * The budget rides along for the same reason: the page prints it as
   * "최대 N초" beside the elapsed count while an answer is being made, and a
   * constant copied into the frontend would drift the next time it moves.
   */
  const fetchAvailability = async (): Promise<{
    available: boolean
    answerTimeoutSeconds: number
  }> => {
    const { data } = await $fetch<{
      data: { available: boolean, answer_timeout_seconds?: number }
    }>(url('/chat/availability'))
    return {
      available: data.available,
      answerTimeoutSeconds: data.answer_timeout_seconds ?? 0
    }
  }

  const fetchThreads = async (): Promise<ThreadSummary[]> =>
    (await $fetch<{ data: ThreadSummary[] }>(url('/chat/threads'))).data

  const fetchThread = async (id: string): Promise<ThreadDetail> =>
    (await $fetch<{ data: ThreadDetail }>(url(`/chat/threads/${id}`))).data

  /** Opens an empty thread. No body: the RAG owns the model and the prompt. */
  const createThread = async (): Promise<ThreadDetail> => {
    const t = (await $fetch<{ data: ThreadDetail }>(url('/chat/threads'), {
      method: 'POST'
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
    fetchThreads, fetchThread,
    createThread, renameThread, deleteThread, sendMessage,
    putFeedback, deleteFeedback
  }
}
