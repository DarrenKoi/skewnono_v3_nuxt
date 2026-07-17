<script setup lang="ts">
import type { ChatMessage } from '~/composables/useChatApi'

const props = defineProps<{ message: ChatMessage; pending?: boolean; error?: boolean }>()

const isUser = computed(() => props.message.role === 'user')
const meta = computed(() => {
  const m = props.message
  const bits: string[] = []
  if (m.latency_ms != null) bits.push(`${m.latency_ms} ms`)
  const tokens = (m.prompt_tokens ?? 0) + (m.completion_tokens ?? 0)
  if (tokens) bits.push(`${tokens} tok`)
  return bits.join(' · ')
})
</script>

<template>
  <div
    class="flex"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap"
      :class="[
        isUser ? 'bg-sky-500 text-white' : 'bg-elevated text-default',
        error ? 'ring-1 ring-error' : ''
      ]"
    >
      <span v-if="pending" class="opacity-70">…</span>
      <template v-else>{{ message.content }}</template>
      <div
        v-if="!isUser && !pending && meta"
        class="sk-meta mt-1 opacity-70"
      >
        {{ meta }}
      </div>
    </div>
  </div>
</template>
