<script setup lang="ts">
import type {
  FeedbackInput,
  FeedbackReason,
  MessageFeedback
} from '~/composables/useChatApi'
import { normalizeFeedbackInput } from '~/utils/chatSources'

const props = defineProps<{
  feedback: MessageFeedback | null
  loading?: boolean
}>()

const emit = defineEmits<{
  submit: [input: FeedbackInput]
  remove: []
}>()

const reasonOptions: Array<{ value: FeedbackReason, label: string }> = [
  { value: 'incorrect', label: '부정확함' },
  { value: 'insufficient_evidence', label: '근거가 부족함' },
  { value: 'wrong_source', label: '출처가 적절하지 않음' },
  { value: 'outdated', label: '정보가 오래됨' },
  { value: 'unclear', label: '설명이 불명확함' },
  { value: 'incorrect_scope_rejection', label: '범위 거절이 잘못됨' },
  { value: 'other', label: '기타' }
]

const panelOpen = ref(false)
const selectedReasons = ref<FeedbackReason[]>([])
const comment = ref('')

const resetDraft = () => {
  selectedReasons.value = props.feedback?.rating === 'down'
    ? [...props.feedback.reasons]
    : []
  comment.value = props.feedback?.rating === 'down'
    ? props.feedback.comment ?? ''
    : ''
}

watch(() => props.feedback, resetDraft, { immediate: true })

const handleUp = () => {
  if (props.loading) return
  panelOpen.value = false
  if (props.feedback?.rating === 'up') {
    emit('remove')
    return
  }
  emit('submit', normalizeFeedbackInput('up', [], ''))
}

const handleDown = () => {
  if (props.loading) return
  if (props.feedback?.rating === 'down') {
    panelOpen.value = false
    emit('remove')
    return
  }
  if (!panelOpen.value) resetDraft()
  panelOpen.value = !panelOpen.value
}

const cancelDown = () => {
  resetDraft()
  panelOpen.value = false
}

const submitDown = () => {
  if (props.loading) return
  emit('submit', normalizeFeedbackInput('down', selectedReasons.value, comment.value))
  panelOpen.value = false
}
</script>

<template>
  <div class="sk-chat-feedback">
    <div
      class="sk-chat-reactions"
      aria-label="답변 평가"
    >
      <button
        type="button"
        class="sk-chat-reaction"
        :class="{ 'is-selected': feedback?.rating === 'up' }"
        :aria-label="feedback?.rating === 'up' ? '긍정 평가 삭제' : '긍정 평가'"
        :aria-pressed="feedback?.rating === 'up'"
        :disabled="loading"
        @click="handleUp"
      >
        <UIcon name="i-lucide-thumbs-up" />
      </button>
      <button
        type="button"
        class="sk-chat-reaction"
        :class="{ 'is-selected': feedback?.rating === 'down' }"
        :aria-label="feedback?.rating === 'down' ? '부정 평가 삭제' : '부정 평가'"
        :aria-pressed="feedback?.rating === 'down'"
        :aria-expanded="panelOpen"
        :disabled="loading"
        @click="handleDown"
      >
        <UIcon name="i-lucide-thumbs-down" />
      </button>
      <UIcon
        v-if="loading"
        name="i-lucide-loader-circle"
        class="sk-chat-feedback-spinner"
        aria-label="평가 저장 중"
      />
    </div>

    <form
      v-if="panelOpen"
      class="sk-chat-feedback-panel"
      aria-label="부정 평가 상세"
      @submit.prevent="submitDown"
    >
      <p class="sk-chat-feedback-title">
        어떤 점이 아쉬웠나요?
      </p>
      <div class="sk-chat-feedback-reasons">
        <label
          v-for="option in reasonOptions"
          :key="option.value"
          class="sk-chat-feedback-reason"
        >
          <input
            v-model="selectedReasons"
            type="checkbox"
            :value="option.value"
            :disabled="loading"
          >
          <span>{{ option.label }}</span>
        </label>
      </div>
      <label class="sk-chat-feedback-comment">
        <span>추가 의견 <span class="sk-chat-feedback-optional">(선택)</span></span>
        <textarea
          v-model="comment"
          rows="2"
          maxlength="500"
          :disabled="loading"
          placeholder="답변 개선에 도움이 되는 내용을 남겨 주세요."
        />
      </label>
      <div class="sk-chat-feedback-actions">
        <button
          type="button"
          class="sk-chat-feedback-cancel"
          :disabled="loading"
          @click="cancelDown"
        >
          취소
        </button>
        <button
          type="submit"
          class="sk-chat-feedback-submit"
          :disabled="loading"
        >
          평가 보내기
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.sk-chat-feedback {
  position: relative;
}

.sk-chat-reactions {
  display: inline-flex;
  align-items: center;
  gap: 0.125rem;
}

.sk-chat-reaction {
  display: inline-grid;
  width: 1.625rem;
  height: 1.625rem;
  place-items: center;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--sk-ink-subtle);
  font-size: 0.8125rem;
  transition: color 0.12s ease, background 0.12s ease;
}

.sk-chat-reaction:hover:not(:disabled),
.sk-chat-reaction.is-selected {
  background: var(--sk-accent-soft);
  color: var(--sk-accent);
}

.sk-chat-reaction:focus-visible,
.sk-chat-feedback-panel button:focus-visible,
.sk-chat-feedback-panel input:focus-visible,
.sk-chat-feedback-panel textarea:focus-visible {
  outline: 2px solid var(--sk-focus-ring);
  outline-offset: 2px;
}

.sk-chat-reaction:disabled,
.sk-chat-feedback-panel :disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.sk-chat-feedback-spinner {
  margin-left: 0.2rem;
  color: var(--sk-ink-subtle);
  animation: sk-chat-feedback-spin 0.8s linear infinite;
}

.sk-chat-feedback-panel {
  width: min(30rem, calc(100vw - 4rem));
  margin-top: 0.375rem;
  padding: 0.75rem;
  border: 1px solid var(--sk-border);
  border-radius: var(--sk-r-card, 0.625rem);
  background: var(--sk-surface);
  box-shadow: 0 0.5rem 1.5rem color-mix(in srgb, var(--sk-ink) 10%, transparent);
}

.sk-chat-feedback-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--sk-ink);
}

.sk-chat-feedback-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem 0.75rem;
  margin-top: 0.625rem;
}

.sk-chat-feedback-reason {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--sk-ink-muted);
  font-size: 0.75rem;
  cursor: pointer;
}

.sk-chat-feedback-reason input {
  accent-color: var(--sk-accent);
}

.sk-chat-feedback-comment {
  display: grid;
  gap: 0.3rem;
  margin-top: 0.75rem;
  color: var(--sk-ink-muted);
  font-size: 0.75rem;
}

.sk-chat-feedback-optional {
  color: var(--sk-ink-subtle);
}

.sk-chat-feedback-comment textarea {
  width: 100%;
  resize: vertical;
  padding: 0.5rem 0.625rem;
  border: 1px solid var(--sk-border);
  border-radius: 0.5rem;
  background: var(--sk-canvas);
  color: var(--sk-ink);
  font-size: 0.8125rem;
  line-height: 1.45;
}

.sk-chat-feedback-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.375rem;
  margin-top: 0.625rem;
}

.sk-chat-feedback-actions button {
  padding: 0.3rem 0.625rem;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.sk-chat-feedback-cancel {
  border: 0;
  background: transparent;
  color: var(--sk-ink-muted);
}

.sk-chat-feedback-submit {
  border: 1px solid var(--sk-accent);
  background: var(--sk-accent);
  color: var(--sk-brand-fg);
}

@keyframes sk-chat-feedback-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .sk-chat-reaction {
    transition: none;
  }

  .sk-chat-feedback-spinner {
    animation: none;
  }
}
</style>
