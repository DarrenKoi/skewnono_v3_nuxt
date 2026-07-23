<script setup lang="ts">
import { formatElapsed } from '~/utils/liveAlarm'
import type { LiveAlarmEvent } from '~/utils/liveAlarm'

const props = defineProps<{
  event: LiveAlarmEvent
  serverOffsetMs: number
  isNew: boolean
  toolSlug: string
  fab: string
}>()

const elapsed = computed(() =>
  formatElapsed(Date.now() + props.serverOffsetMs - props.event.occurred_epoch * 1000)
)

// Checking the recipe is the natural next action after seeing the alarm.
const recipeLink = computed(() =>
  props.event.recipe_id
    ? `/ebeam/${props.toolSlug}/${props.fab}/recipe-search?q=${encodeURIComponent(props.event.recipe_id)}`
    : null
)
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-default px-4 py-3 transition-colors duration-1000 last:border-b-0"
    :class="isNew ? 'bg-(--sk-accent-tint)' : 'bg-transparent'"
  >
    <UBadge
      :color="event.kind === 'align' ? 'error' : 'warning'"
      variant="subtle"
    >
      {{ event.kind === 'align' ? 'Align Fail' : '측정 연속 실패' }}
    </UBadge>

    <span class="text-lg font-semibold tracking-tight">{{ event.eqp_id }}</span>

    <span class="text-sm text-muted">{{ elapsed }}</span>

    <NuxtLink
      v-if="recipeLink"
      :to="recipeLink"
      class="text-sm underline"
    >
      {{ event.recipe_id }}
    </NuxtLink>
    <span
      v-else
      class="text-sm text-muted"
    >레시피 정보 없음</span>

    <span class="ml-auto text-xs text-muted">
      {{ event.operation_desc }}
      <template v-if="event.lot_type_cd"> · {{ event.lot_type_cd }}</template>
    </span>
  </div>
</template>
