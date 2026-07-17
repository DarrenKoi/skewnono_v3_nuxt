<script setup lang="ts">
import type { ThreadSummary } from '~/composables/useChatApi'
import { formatRelativeTime } from '~/utils/relativeTime'

defineProps<{ threads: ThreadSummary[], activeId: string | null }>()
const emit = defineEmits<{
  select: [id: string]
  create: []
  remove: [id: string]
}>()

// "meta-llama/llama-3.3-70b-instruct:free" -> "llama-3.3-70b-instruct"
const shortModel = (id: string) =>
  (id.split('/').pop() ?? id).replace(/:free$/, '')
</script>

<template>
  <aside class="sk-sidebar">
    <div class="sk-sidebar-head">
      <UButton
        block
        icon="i-lucide-plus"
        label="새 대화"
        color="neutral"
        @click="emit('create')"
      />
    </div>

    <p class="sk-sidebar-eyebrow">
      대화
    </p>

    <div class="sk-sidebar-list">
      <button
        v-for="t in threads"
        :key="t.id"
        type="button"
        class="sk-thread"
        :class="{ 'sk-thread-active': t.id === activeId }"
        @click="emit('select', t.id)"
      >
        <span
          class="sk-thread-bar"
          aria-hidden="true"
        />
        <span class="sk-thread-body">
          <span class="sk-thread-title">{{ t.title }}</span>
          <span class="sk-thread-meta">
            {{ shortModel(t.model) }} · {{ formatRelativeTime(t.updated_at) }}
          </span>
        </span>
        <UButton
          icon="i-lucide-trash-2"
          color="neutral"
          variant="ghost"
          size="xs"
          class="sk-thread-del"
          aria-label="대화 삭제"
          @click.stop="emit('remove', t.id)"
        />
      </button>

      <p
        v-if="!threads.length"
        class="sk-sidebar-empty"
      >
        아직 대화가 없습니다.
      </p>
    </div>
  </aside>
</template>

<style scoped>
.sk-sidebar {
  width: 16rem;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--sk-border-soft);
  background: var(--sk-surface);
}

.sk-sidebar-head {
  padding: 0.75rem;
}

.sk-sidebar-eyebrow {
  padding: 0.25rem 1rem 0.5rem;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--sk-ink-subtle);
}

.sk-sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 0.5rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.sk-thread {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.5rem 0.5rem 0.5rem 0.625rem;
  border-radius: 0.5rem;
  text-align: left;
  transition: background 0.12s ease;
}

.sk-thread:hover {
  background: var(--sk-muted-surface);
}

.sk-thread-active {
  background: var(--sk-accent-tint);
}

.sk-thread:focus-visible {
  outline: 2px solid var(--sk-focus-ring);
  outline-offset: -2px;
}

.sk-thread-bar {
  position: absolute;
  left: 0;
  top: 0.5rem;
  bottom: 0.5rem;
  width: 2px;
  border-radius: 1px;
  background: transparent;
}

.sk-thread-active .sk-thread-bar {
  background: var(--sk-accent);
}

.sk-thread-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.0625rem;
}

.sk-thread-title {
  font-size: 0.875rem;
  color: var(--sk-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sk-thread-meta {
  font-size: 0.6875rem;
  color: var(--sk-ink-subtle);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sk-thread-del {
  opacity: 0;
  flex-shrink: 0;
  transition: opacity 0.12s ease;
}

.sk-thread:hover .sk-thread-del,
.sk-thread-del:focus-visible {
  opacity: 1;
}

.sk-sidebar-empty {
  padding: 0.5rem 0.625rem;
  font-size: 0.8125rem;
  color: var(--sk-ink-subtle);
}

@media (prefers-reduced-motion: reduce) {
  .sk-thread,
  .sk-thread-del {
    transition: none;
  }
}
</style>
