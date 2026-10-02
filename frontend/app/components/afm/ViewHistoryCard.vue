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
        size="xs"
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
        class="group flex items-start gap-2 px-4 py-2.5 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
      >
        <button
          type="button"
          class="min-w-0 flex-1 space-y-1 text-left"
          @click="$emit('view-details', item)"
        >
          <span class="flex items-baseline gap-2">
            <span class="shrink-0 font-mono text-xs tabular-nums text-(--sk-ink-muted)">
              {{ item.formattedDate }}
            </span>
            <span class="truncate text-sm font-semibold text-(--sk-ink)">
              {{ item.recipeName }}
            </span>
          </span>
          <span class="flex flex-wrap items-center gap-x-2 gap-y-1">
            <AfmLotSlotTags
              :lot-id="item.lotId"
              :slot-number="item.slotNumber"
            />
            <UBadge
              :label="item.measuredInfo"
              color="neutral"
              variant="outline"
            />
            <span class="sk-meta">
              {{ formatKoreanDateTime(item.viewedAt) }}
            </span>
          </span>
        </button>
        <UButton
          size="xs"
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
      class="px-4 py-6 text-center sk-body"
    >
      조회 기록이 없습니다.
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
