<template>
  <div
    v-if="visible.length"
    class="space-y-2.5"
  >
    <div
      v-for="row in visible"
      :key="row.model"
      class="space-y-1"
    >
      <div class="flex items-center justify-between text-xs">
        <span
          class="font-medium text-(--sk-ink) truncate"
          :title="row.model"
        >
          {{ row.model }}
          <span class="text-zinc-500 font-normal ml-1">{{ row.tool_count }}대</span>
        </span>
        <span class="text-zinc-500 tabular-nums shrink-0 ml-2">
          {{ row.count }}
        </span>
      </div>
      <div class="h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
        <div
          class="h-full bg-gradient-to-r from-sky-400 to-violet-500"
          :style="{ width: `${pctOf(row.count)}%` }"
        />
      </div>
    </div>
  </div>
  <div
    v-else
    class="text-sm text-zinc-500"
  >
    {{ emptyText }}
  </div>
</template>

<script setup lang="ts">
import type { SemModelCount } from '~/composables/useActivityApi'

const props = withDefaults(
  defineProps<{
    items: SemModelCount[]
    emptyText?: string
    cap?: number
  }>(),
  { emptyText: '—', cap: 8 }
)

const visible = computed(() => props.items.slice(0, props.cap))
// Share bars scale to the busiest model so relative traffic is readable
// at a glance, same policy as FeatureBarList.
const maxCount = computed(() => visible.value.reduce((m, r) => Math.max(m, r.count), 0))
const pctOf = (n: number) => {
  if (maxCount.value <= 0) return 0
  return Math.max(2, Math.round((n * 100) / maxCount.value))
}
</script>
