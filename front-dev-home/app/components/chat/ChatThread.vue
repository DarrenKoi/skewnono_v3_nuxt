<script setup lang="ts">
import type { ChatMessage } from '~/composables/useChatApi'

defineProps<{
  messages: ChatMessage[]
  pending?: boolean
  errorMessage?: string | null
}>()
const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="flex-1 overflow-y-auto p-4 space-y-3">
    <ChatMessage
      v-for="m in messages"
      :key="m.id"
      :message="m"
    />
    <ChatMessage
      v-if="pending"
      :message="{ id: 'pending', thread_id: '', role: 'assistant', content: '', created_at: '' }"
      pending
    />
    <div v-if="errorMessage" class="flex justify-start">
      <div class="max-w-[80%] rounded-lg px-3 py-2 text-sm bg-elevated ring-1 ring-error">
        <p class="text-error">{{ errorMessage }}</p>
        <UButton
          size="xs"
          variant="ghost"
          icon="i-lucide-rotate-cw"
          label="다시 시도"
          class="mt-1"
          @click="emit('retry')"
        />
      </div>
    </div>
    <p v-if="!messages.length && !pending" class="sk-meta text-center mt-8">
      메시지를 보내 대화를 시작하세요.
    </p>
  </div>
</template>
