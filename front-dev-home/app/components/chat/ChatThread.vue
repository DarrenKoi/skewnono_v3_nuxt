<script setup lang="ts">
import type { ChatMessage, FeedbackInput } from '~/composables/useChatApi'

const props = defineProps<{
  messages: ChatMessage[]
  pending?: boolean
  errorMessage?: string | null
  feedbackLoadingIds?: ReadonlySet<string>
}>()
const emit = defineEmits<{
  retry: []
  example: [text: string]
  feedback: [messageId: string, input: FeedbackInput | null]
}>()

const isFeedbackLoading = (messageId: string): boolean =>
  props.feedbackLoadingIds?.has(messageId) ?? false

const scroller = ref<HTMLElement | null>(null)
const scrollToEnd = () => {
  nextTick(() => {
    const el = scroller.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
// Keep the newest turn in view as messages arrive or the typing dots appear.
watch(() => [props.messages.length, props.pending, props.errorMessage], scrollToEnd)
onMounted(scrollToEnd)

const examples = [
  '이 데이터를 요약해 줘',
  '파이썬으로 CSV를 읽는 코드를 보여줘',
  '계측 용어 SPC를 쉽게 설명해 줘'
]
</script>

<template>
  <div
    ref="scroller"
    class="sk-chat-scroller flex-1 overflow-y-auto"
  >
    <div class="sk-chat-column">
      <!-- Empty state: welcome + starter prompts -->
      <div
        v-if="!messages.length && !pending && !errorMessage"
        class="sk-chat-empty"
      >
        <div class="sk-chat-empty-mark">
          <UIcon name="i-lucide-sparkles" />
        </div>
        <h2 class="sk-chat-empty-title">
          무엇을 도와드릴까요?
        </h2>
        <p class="sk-chat-empty-sub">
          SKEWNONO 에 대해 궁금한 것을 물어보세요.
        </p>
        <div class="sk-chat-examples">
          <button
            v-for="ex in examples"
            :key="ex"
            type="button"
            class="sk-chat-example"
            @click="emit('example', ex)"
          >
            {{ ex }}
          </button>
        </div>
      </div>

      <!-- Conversation -->
      <div
        v-else
        class="space-y-5 py-5"
      >
        <ChatMessage
          v-for="m in messages"
          :key="m.id"
          :message="m"
          :feedback-loading="isFeedbackLoading(m.id)"
          @feedback="(messageId, input) => emit('feedback', messageId, input)"
          @follow-up="text => emit('example', text)"
        />

        <!-- Typing indicator -->
        <div
          v-if="pending"
          class="sk-chat-assistant flex gap-3"
        >
          <div
            class="sk-chat-avatar"
            aria-hidden="true"
          >
            <UIcon name="i-lucide-sparkles" />
          </div>
          <div
            class="sk-chat-typing"
            role="status"
            aria-label="응답 생성 중"
          >
            <span /><span /><span />
          </div>
        </div>

        <!-- Error with retry -->
        <div
          v-if="errorMessage"
          class="sk-chat-error"
          role="alert"
        >
          <div class="flex items-start gap-2">
            <UIcon
              name="i-lucide-triangle-alert"
              class="sk-chat-error-icon"
            />
            <p class="flex-1">
              {{ errorMessage }}
            </p>
          </div>
          <UButton
            size="xs"
            variant="soft"
            color="error"
            icon="i-lucide-rotate-cw"
            label="다시 시도"
            class="mt-2"
            @click="emit('retry')"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sk-chat-scroller {
  scroll-behavior: smooth;
}

.sk-chat-column {
  width: 100%;
  max-width: 46rem;
  margin: 0 auto;
  padding: 0 1.25rem;
}

/* Empty state */
.sk-chat-empty {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 3rem 0;
}

.sk-chat-empty-mark {
  width: 3rem;
  height: 3rem;
  display: grid;
  place-items: center;
  border-radius: 0.875rem;
  background: var(--sk-accent-soft);
  color: var(--sk-accent);
  font-size: 1.5rem;
  margin-bottom: 1rem;
}

.sk-chat-empty-title {
  font-size: 1.375rem;
  font-weight: 600;
  color: var(--sk-ink);
}

.sk-chat-empty-sub {
  margin-top: 0.375rem;
  font-size: 0.875rem;
  color: var(--sk-ink-muted);
}

.sk-chat-examples {
  margin-top: 1.5rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  max-width: 32rem;
}

.sk-chat-example {
  padding: 0.5rem 0.875rem;
  border-radius: 999px;
  border: 1px solid var(--sk-border);
  background: var(--sk-surface);
  color: var(--sk-ink-muted);
  font-size: 0.8125rem;
  transition: border-color 0.12s ease, color 0.12s ease, background 0.12s ease;
}

.sk-chat-example:hover {
  border-color: var(--sk-accent-border);
  color: var(--sk-ink);
  background: var(--sk-accent-tint);
}

.sk-chat-example:focus-visible {
  outline: 2px solid var(--sk-focus-ring);
  outline-offset: 2px;
}

/* Typing indicator */
.sk-chat-typing {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.6rem 0.25rem;
}

.sk-chat-typing span {
  width: 0.4rem;
  height: 0.4rem;
  border-radius: 50%;
  background: var(--sk-ink-subtle);
  animation: sk-chat-bounce 1.1s ease-in-out infinite;
}

.sk-chat-typing span:nth-child(2) {
  animation-delay: 0.18s;
}

.sk-chat-typing span:nth-child(3) {
  animation-delay: 0.36s;
}

@keyframes sk-chat-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-0.28rem);
    opacity: 1;
  }
}

/* Error */
.sk-chat-error {
  border: 1px solid var(--sk-bad-border);
  background: var(--sk-bad-soft);
  color: var(--sk-bad);
  border-radius: var(--sk-r-card, 0.625rem);
  padding: 0.75rem 0.875rem;
  font-size: 0.875rem;
  max-width: 42rem;
}

.sk-chat-error-icon {
  margin-top: 0.1rem;
  flex-shrink: 0;
}

@media (prefers-reduced-motion: reduce) {
  .sk-chat-scroller {
    scroll-behavior: auto;
  }
  .sk-chat-typing span {
    animation: none;
    opacity: 0.7;
  }
  .sk-chat-example {
    transition: none;
  }
}
</style>
