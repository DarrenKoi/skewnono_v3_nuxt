<script setup lang="ts">
import type { ThreadSummary } from '~/composables/useChatApi'

defineProps<{ threads: ThreadSummary[]; activeId: string | null }>()
const emit = defineEmits<{
  select: [id: string]
  create: []
  remove: [id: string]
}>()
</script>

<template>
  <aside class="w-64 shrink-0 border-r border-default flex flex-col">
    <div class="p-3">
      <UButton
        block
        icon="i-lucide-plus"
        label="새 대화"
        @click="emit('create')"
      />
    </div>
    <div class="flex-1 overflow-y-auto">
      <div
        v-for="t in threads"
        :key="t.id"
        class="group flex items-center gap-1 px-3 py-2 cursor-pointer hover:bg-elevated"
        :class="t.id === activeId ? 'bg-elevated' : ''"
        @click="emit('select', t.id)"
      >
        <span class="flex-1 truncate text-sm">{{ t.title }}</span>
        <UButton
          icon="i-lucide-trash-2"
          color="neutral"
          variant="ghost"
          size="xs"
          class="opacity-0 group-hover:opacity-100"
          @click.stop="emit('remove', t.id)"
        />
      </div>
      <p v-if="!threads.length" class="sk-meta px-3 py-2">대화가 없습니다.</p>
    </div>
  </aside>
</template>
