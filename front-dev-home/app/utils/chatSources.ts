import type {
  ChatMessage,
  FeedbackInput,
  FeedbackReason,
  MessageFeedback,
  SourceRef
} from '~/composables/useChatApi'

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
