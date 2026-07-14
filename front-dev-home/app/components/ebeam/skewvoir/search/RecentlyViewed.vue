<template>
  <section class="dashboard-surface flex flex-col rounded-(--sk-r-card)">
    <header class="flex items-center justify-between gap-2 border-b border-(--sk-border-soft) px-3 py-2">
      <div class="flex items-baseline gap-2">
        <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
          최근 본 측정
        </h2>
        <span class="font-mono text-[10.5px] text-(--sk-ink-subtle)">{{ items.length }}</span>
      </div>
      <UButton
        v-if="items.length"
        color="neutral"
        variant="ghost"
        size="xs"
        label="전체 삭제"
        @click="emit('clear')"
      />
    </header>

    <p
      v-if="!items.length"
      class="px-4 py-10 text-center text-[12px] text-(--sk-ink-muted)"
    >
      아직 연 측정이 없습니다. 검색 결과에서 측정을 열면 여기에 쌓입니다.
    </p>

    <table
      v-else
      class="w-full border-collapse text-[12px]"
    >
      <tbody>
        <tr
          v-for="item in items"
          :key="item.msr"
          class="group border-b border-(--sk-border-soft) transition-colors last:border-0"
          :class="item.expired
            ? 'cursor-not-allowed opacity-50'
            : 'cursor-pointer hover:bg-(--sk-brand)/5'"
          @click="!item.expired && emit('open', item)"
        >
          <td class="px-3 py-2 font-mono font-semibold text-zinc-900 dark:text-zinc-100">
            {{ item.lot }}
          </td>
          <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
            {{ item.recipe }}
          </td>
          <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
            {{ item.eq }}
          </td>
          <td class="px-3 py-2 font-mono text-(--sk-ink-muted)">
            {{ item.capturedAt.slice(0, 10) }}
          </td>
          <td class="px-3 py-2">
            <!-- Remembered, but the data is gone. Saying so beats silently
                 dropping a row the user knows they looked at. -->
            <span
              v-if="item.expired"
              class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-1.5 py-0.5 font-mono text-[10.5px] text-(--sk-ink-muted)"
            >
              보존 기간 만료
            </span>
          </td>
          <td
            class="px-3 py-2 text-right"
            @click.stop
          >
            <button
              type="button"
              class="opacity-0 transition-opacity group-hover:opacity-100"
              @click="emit('remove', item.msr)"
            >
              <UIcon
                name="i-lucide-x"
                class="h-3.5 w-3.5 text-(--sk-ink-muted) hover:text-(--sk-bad)"
              />
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import type { SkewvoirRecentEntry } from '~/composables/useSkewvoirRecentlyViewed'

defineProps<{
  items: SkewvoirRecentEntry[]
}>()

const emit = defineEmits<{
  open: [item: SkewvoirRecentEntry]
  remove: [msr: string]
  clear: []
}>()
</script>
