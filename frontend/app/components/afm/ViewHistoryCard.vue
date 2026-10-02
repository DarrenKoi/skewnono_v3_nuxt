<template>
  <AfmCard
    icon="i-lucide-eye"
    title="조회 기록"
    :count="items.length"
    flush
  >
    <template
      v-if="items.length"
      #actions
    >
      <UButton
        size="sm"
        color="neutral"
        variant="ghost"
        label="전체 삭제"
        @click="$emit('clear')"
      />
    </template>

    <ul
      v-if="items.length"
      class="divide-y divide-(--sk-border-soft)"
    >
      <li
        v-for="item in items"
        :key="item.filename"
        class="group flex items-start gap-2 px-4 py-3 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
      >
        <button
          type="button"
          class="min-w-0 flex-1 text-left"
          @click="$emit('view-details', item)"
        >
          <AfmMeasurementSummary :measurement="item" />
          <span class="mt-1 block sk-meta">
            {{ formatKoreanDateTime(item.viewedAt) }} 조회
          </span>
        </button>
        <UButton
          size="sm"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="조회 기록에서 삭제"
          class="opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
          @click="$emit('remove', item.filename)"
        />
      </li>
    </ul>
    <p
      v-else
      class="px-4 py-5 text-center sk-body"
    >
      조회 기록이 없습니다.
      <span class="mt-1 block sk-meta">측정을 열면 최근 10건이 여기에 남습니다.</span>
    </p>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmHistoryEntry } from '~/composables/useAfmCart'

defineProps<{
  items: AfmHistoryEntry[]
}>()

defineEmits<{
  'view-details': [item: AfmHistoryEntry]
  'remove': [filename: string]
  'clear': []
}>()
</script>
