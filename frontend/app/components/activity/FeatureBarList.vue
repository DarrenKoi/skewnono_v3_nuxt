<template>
  <div
    v-if="visible.length"
    class="space-y-2.5"
  >
    <div
      v-for="row in visible"
      :key="row.feature"
      class="space-y-1"
    >
      <div class="flex items-center justify-between text-xs">
        <span
          class="sk-value truncate"
          :title="row.feature"
        >
          {{ activityFeatureLabel(row.feature) }}
        </span>
        <span class="sk-meta tabular-nums shrink-0 ml-2">
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
    class="sk-body"
  >
    {{ emptyText }}
  </div>
</template>

<script setup lang="ts">
import type { FeatureCount } from '~/composables/useActivityApi'
import { activityFeatureLabel } from '~/utils/activity'

const props = withDefaults(
  defineProps<{
    items: FeatureCount[]
    emptyText?: string
    cap?: number
  }>(),
  { emptyText: '—', cap: 10 }
)

const visible = computed(() => props.items.slice(0, props.cap))
const maxCount = computed(() => visible.value.reduce((m, r) => Math.max(m, r.count), 0))
const pctOf = (n: number) => {
  if (maxCount.value <= 0) return 0
  return Math.max(2, Math.round((n * 100) / maxCount.value))
}
</script>
