<script setup lang="ts">
import type { SourceRef } from '~/composables/useChatApi'
import { formatSourceLabel } from '~/utils/chatSources'

defineProps<{ sources: SourceRef[] }>()
</script>

<template>
  <section
    v-if="sources.length"
    class="sk-chat-sources"
    aria-label="참고 출처"
  >
    <span class="sk-chat-sources-label">출처</span>
    <ul class="sk-chat-source-list">
      <li
        v-for="source in sources"
        :key="source.source_id"
      >
        <!-- Source locators are internal identifiers, not navigable URLs. -->
        <span
          class="sk-chat-source-chip"
          :title="source.snippet"
        >
          <UIcon
            name="i-lucide-file-text"
            aria-hidden="true"
          />
          {{ formatSourceLabel(source) }}
        </span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.sk-chat-sources {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-top: 0.625rem;
}

.sk-chat-sources-label {
  flex-shrink: 0;
  padding-top: 0.2rem;
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--sk-ink-subtle);
}

.sk-chat-source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.sk-chat-source-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  max-width: 100%;
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--sk-border-soft);
  border-radius: 999px;
  background: var(--sk-muted-surface);
  color: var(--sk-ink-muted);
  font-size: 0.6875rem;
  line-height: 1.35;
}

.sk-chat-source-chip svg {
  flex-shrink: 0;
}
</style>
