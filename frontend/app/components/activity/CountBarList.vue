<template>
  <div
    v-if="visible.length"
    class="space-y-2.5"
  >
    <div
      v-for="row in visible"
      :key="row.label"
      class="space-y-1"
    >
      <div class="flex items-baseline justify-between gap-2 text-xs">
        <span class="min-w-0 truncate">
          <span class="sk-value">{{ row.label }}</span>
          <span
            v-if="row.hint"
            class="sk-meta ml-1.5"
          >{{ row.hint }}</span>
        </span>
        <span class="sk-meta tabular-nums shrink-0">
          {{ row.count.toLocaleString() }}{{ unit }}
        </span>
      </div>
      <!-- Same track and fill as ActivityFeatureBarList, so the two read as
           one kind of list on pages that show both. -->
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
import type { CountRow } from '~/utils/activityVisitors'

// ActivityFeatureBarList's shape for rows that are not features: it runs every
// label through activityFeatureLabel, which would rewrite a person's or a
// team's name as if it were a slug.
const props = withDefaults(
  defineProps<{
    items: CountRow[]
    unit?: string
    emptyText?: string
    cap?: number
  }>(),
  { unit: '', emptyText: '—', cap: 10 }
)

const visible = computed(() => props.items.slice(0, props.cap))
const maxCount = computed(() => visible.value.reduce((max, row) => Math.max(max, row.count), 0))
// A zero row keeps an empty track: unlike a ranking, these lists show bands
// that can legitimately hold nobody.
const pctOf = (count: number) =>
  maxCount.value <= 0 || count <= 0 ? 0 : Math.max(2, Math.round((count * 100) / maxCount.value))
</script>
