<template>
  <ol
    v-if="items.length"
    class="space-y-2"
  >
    <li
      v-for="(row, index) in items"
      :key="row.feature"
      class="flex items-center justify-between gap-2 text-xs"
    >
      <span class="flex items-center gap-2 min-w-0">
        <!-- The rank is the whole point of the list, so it is drawn rather
             than implied: without it the rows read as an unordered set and
             the reader has to infer the order from the times. A numeral in
             subtle ink, not a filled badge — DESIGN.md reserves ink fills for
             things that navigate and terracotta for things that filter, and
             this ranks. -->
        <span class="w-4 shrink-0 tabular-nums text-(--sk-ink-subtle)">
          {{ index + 1 }}
        </span>
        <span
          class="sk-value truncate"
          :title="row.feature"
        >
          {{ activityFeatureLabel(row.feature) }}
        </span>
      </span>
      <span
        class="sk-meta shrink-0 tabular-nums"
        :title="formatKoreanDateTime(row.at)"
      >
        {{ formatRelativeTime(row.at) }}
      </span>
    </li>
  </ol>
  <div
    v-else
    class="sk-body"
  >
    {{ emptyText }}
  </div>
</template>

<script setup lang="ts">
import type { FeatureUse } from '~/composables/useActivityApi'
import { activityFeatureLabel } from '~/utils/activity'
import { formatKoreanDateTime } from '~/utils/dateTime'
import { formatRelativeTime } from '~/utils/relativeTime'

// No `cap` prop: both providers already cap at RECENT_FEATURES_CAP, so a
// second limit here could only ever disagree with the one that matters.
withDefaults(
  defineProps<{
    items: FeatureUse[]
    emptyText?: string
  }>(),
  { emptyText: '—' }
)
</script>
