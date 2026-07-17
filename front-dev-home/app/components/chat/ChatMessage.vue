<script setup lang="ts">
import type { ChatMessage } from '~/composables/useChatApi'
import { renderChatMarkdown } from '~/utils/chatMarkdown'
import { formatRelativeTime } from '~/utils/relativeTime'

const props = defineProps<{ message: ChatMessage }>()

const isUser = computed(() => props.message.role === 'user')
const html = computed(() => renderChatMarkdown(props.message.content))

const meta = computed(() => {
  const m = props.message
  const bits: string[] = []
  if (m.latency_ms != null) bits.push(`${(m.latency_ms / 1000).toFixed(1)}초`)
  const tokens = (m.prompt_tokens ?? 0) + (m.completion_tokens ?? 0)
  if (tokens) bits.push(`${tokens} 토큰`)
  return bits
})
const time = computed(() =>
  props.message.created_at ? formatRelativeTime(props.message.created_at) : ''
)

const copied = ref(false)
const copy = async () => {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    setTimeout(() => (copied.value = false), 1400)
  } catch {
    // Clipboard unavailable (e.g. insecure context) — silently no-op.
  }
}
</script>

<template>
  <!-- User turn: quiet, right-aligned -->
  <div
    v-if="isUser"
    class="flex justify-end"
  >
    <div class="sk-chat-bubble-user">
      {{ message.content }}
    </div>
  </div>

  <!-- Assistant turn: the signature lane — avatar, name, prose, meta rail -->
  <div
    v-else
    class="sk-chat-assistant group flex gap-3"
  >
    <div
      class="sk-chat-avatar"
      aria-hidden="true"
    >
      <UIcon name="i-lucide-sparkles" />
    </div>
    <div class="min-w-0 flex-1">
      <div class="mb-1 flex items-center gap-2">
        <span class="sk-chat-author">어시스턴트</span>
        <span
          v-if="time"
          class="sk-chat-time"
        >{{ time }}</span>
      </div>
      <!-- content is HTML-escaped inside renderChatMarkdown (see its tests) -->
      <!-- eslint-disable vue/no-v-html -->
      <div
        class="sk-chat-prose"
        v-html="html"
      />
      <!-- eslint-enable vue/no-v-html -->
      <div class="sk-chat-metarail">
        <span
          v-for="bit in meta"
          :key="bit"
          class="sk-chat-metachip"
        >{{ bit }}</span>
        <UButton
          :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'"
          :label="copied ? '복사됨' : '복사'"
          color="neutral"
          variant="ghost"
          size="xs"
          class="sk-chat-copy"
          @click="copy"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.sk-chat-bubble-user {
  max-width: 78%;
  padding: 0.5rem 0.875rem;
  border-radius: 1rem 1rem 0.25rem 1rem;
  background: var(--sk-brand);
  color: var(--sk-brand-fg);
  font-size: 0.9375rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.sk-chat-avatar {
  flex-shrink: 0;
  width: 1.875rem;
  height: 1.875rem;
  display: grid;
  place-items: center;
  border-radius: 0.5rem;
  background: var(--sk-accent-soft);
  color: var(--sk-accent);
  font-size: 1rem;
}

.sk-chat-author {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--sk-ink);
}

.sk-chat-time {
  font-size: 0.75rem;
  color: var(--sk-ink-subtle);
}

.sk-chat-prose {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--sk-ink);
  word-break: break-word;
}

.sk-chat-prose :deep(a) {
  color: var(--sk-accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.sk-chat-prose :deep(.sk-chat-code-inline) {
  padding: 0.05rem 0.3rem;
  border-radius: 0.3rem;
  background: var(--sk-muted-surface);
  border: 1px solid var(--sk-border-soft);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.85em;
}

.sk-chat-prose :deep(.sk-chat-code-block) {
  margin: 0.5rem 0;
  padding: 0.75rem 0.875rem;
  border-radius: var(--sk-r-card, 0.625rem);
  background: var(--sk-muted-surface);
  border: 1px solid var(--sk-border-soft);
  overflow-x: auto;
}

.sk-chat-prose :deep(.sk-chat-code-block code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--sk-ink);
  white-space: pre;
}

.sk-chat-metarail {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.375rem;
  min-height: 1.25rem;
}

.sk-chat-metachip {
  font-size: 0.6875rem;
  color: var(--sk-ink-subtle);
  letter-spacing: 0.01em;
}

.sk-chat-copy {
  opacity: 0;
  transition: opacity 0.12s ease;
}

.sk-chat-assistant:hover .sk-chat-copy,
.sk-chat-copy:focus-visible {
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .sk-chat-copy {
    transition: none;
  }
}
</style>
