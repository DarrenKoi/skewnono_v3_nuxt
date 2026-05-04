<template>
  <section class="dashboard-surface rounded-2xl">
    <header class="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
      <div class="flex items-center gap-2">
        <UIcon name="i-lucide-eye" class="h-4 w-4 text-zinc-500" />
        <h3 class="text-sm font-semibold">
          View History
        </h3>
        <UBadge :label="String(items.length)" color="neutral" size="xs" variant="subtle" />
      </div>
      <UButton
        v-if="items.length > 0"
        size="xs"
        color="neutral"
        variant="ghost"
        @click="$emit('clear')"
      >
        Clear All
      </UButton>
    </header>

    <ul
      v-if="items.length > 0"
      class="divide-y divide-zinc-200 dark:divide-zinc-800"
    >
      <li
        v-for="item in items"
        :key="item.filename"
        class="group flex items-start gap-2 px-4 py-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
      >
        <button
          type="button"
          class="min-w-0 flex-1 cursor-pointer text-left"
          @click="$emit('view-details', item)"
        >
          <p class="truncate text-xs font-medium">
            {{ item.formattedDate }} • {{ item.recipeName }} • {{ item.lotId }}
          </p>
          <p class="truncate text-[11px] text-zinc-500">
            Slot {{ item.slotNumber }} · {{ item.measuredInfo }} · {{ formatViewedAt(item.viewedAt) }}
          </p>
        </button>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="Remove from history"
          class="opacity-0 transition group-hover:opacity-100"
          @click="$emit('remove', item.filename)"
        />
      </li>
    </ul>
    <p
      v-else
      class="px-4 py-6 text-center text-xs text-zinc-500"
    >
      No view history yet
    </p>
  </section>
</template>

<script setup lang="ts">
import type { AfmHistoryEntry } from '~/composables/useAfmCart'

defineProps<{
  items: AfmHistoryEntry[]
}>()

defineEmits<{
  (event: 'view-details', item: AfmHistoryEntry): void
  (event: 'remove', filename: string): void
  (event: 'clear'): void
}>()

const formatViewedAt = (iso: string) => {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}
</script>
