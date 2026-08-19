import type {
  ChatMessage,
  FeedbackInput,
  FeedbackReason,
  MessageFeedback,
  SourceRef
} from '~/composables/useChatApi'
// Relative with an explicit extension, not the `~` alias: this module is
// covered by `npm test` (node --test), which resolves no Nuxt aliases. Type
// imports above are erased before they reach the runner, so only value
// imports need this — same reason `useMsrImageApi.ts` does it.
import { joinApiPath } from './apiPath.ts'

/**
 * Where a figure-bearing citation's image lives.
 *
 * `figure_id` is an opaque token, never a storage key — the server owns the
 * directory (or bucket) and the `.webp` extension. Encoded per segment so a
 * malformed id cannot reshape the path; the office's dots survive that
 * untouched, which matters because the route matches them literally.
 */
export const figureUrl = (base: string, figureId: string): string =>
  `${joinApiPath(base, '/chat/figures')}/${encodeURIComponent(figureId)}`

export const FEEDBACK_REASON_ORDER = [
  'incorrect',
  'insufficient_evidence',
  'wrong_source',
  'outdated',
  'unclear',
  'incorrect_scope_rejection',
  'other'
] as const satisfies readonly FeedbackReason[]

export const formatSourceLabel = (source: SourceRef): string => {
  if (source.source_type !== 'manual') {
    return [source.title, source.occurred_at?.slice(0, 10)]
      .filter(Boolean)
      .join(' · ')
  }

  return [
    source.title,
    source.revision,
    source.page == null ? null : `p.${source.page}`
  ].filter(Boolean).join(' · ')
}

export const normalizeFeedbackInput = (
  rating: FeedbackInput['rating'],
  reasons: readonly string[],
  comment: string
): FeedbackInput => {
  const normalizedComment = comment.trim().slice(0, 500)
  const selectedReasons = new Set(reasons)
  return {
    rating,
    reasons: FEEDBACK_REASON_ORDER.filter(reason => selectedReasons.has(reason)),
    comment: normalizedComment || null
  }
}

type FeedbackThreadTarget = {
  id: string
  messages: Array<Pick<ChatMessage, 'id' | 'role' | 'feedback'>>
}

export const reconcileMessageFeedback = (
  activeThread: FeedbackThreadTarget | null,
  targetThreadId: string,
  messageId: string,
  feedback: MessageFeedback | null
): boolean => {
  if (activeThread?.id !== targetThreadId) return false

  const message = activeThread.messages.find(item => item.id === messageId)
  if (!message || message.role !== 'assistant') return false

  message.feedback = feedback
  return true
}
