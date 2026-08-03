<script setup lang="ts">
import { formatElapsed, KIND_LABEL } from '~/utils/liveAlarm'
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
// recipe_id, not ppid: the two always carry the same value (office-confirmed
// 2026-08-03), so the tiebreak is that recipe-search indexes this spelling.
const recipeLink = computed(() =>
  props.event.recipe_id
    ? `/ebeam/${props.toolSlug}/${props.fab}/recipe-search?q=${encodeURIComponent(props.event.recipe_id)}`
    : null
)

// AL_TYPE is free text from the tool. Only 'warning' gets its own tone; an
// unrecognized value renders as itself rather than being dropped, since a
// value we have not seen before is exactly what we want surfaced.
const alTypeTone = computed(() =>
  props.event.al_type.toLowerCase() === 'warning' ? 'warning' as const : 'neutral' as const
)

// The third line: context needed to place the alarm, none of it worth a column
// of its own. Blank fields drop out entirely rather than rendering a label
// with nothing after it — every field is always present as "" (see
// contracts.py), so absence is a value, not a missing key.
const details = computed(() => [
  { label: 'LOT', value: props.event.lot_id },
  { label: 'FOUP', value: props.event.cassette_id },
  { label: 'STEP', value: props.event.operation_desc || props.event.step_id },
  { label: '이벤트', value: props.event.meseventname },
  { label: '상태', value: props.event.eq_stat }
].filter(detail => detail.value))
</script>

<template>
  <div
    class="border-b border-default px-4 py-3 transition-colors duration-1000 last:border-b-0"
    :class="isNew ? 'bg-(--sk-accent-tint)' : 'bg-transparent'"
  >
    <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
      <UBadge
        :color="event.kind === 'align' ? 'error' : 'warning'"
        variant="subtle"
      >
        {{ KIND_LABEL[event.kind] }}
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

      <span class="ml-auto flex items-center gap-2">
        <UBadge
          v-if="event.al_type"
          :color="alTypeTone"
          variant="subtle"
          size="sm"
        >
          {{ event.al_type }}
        </UBadge>
        <span
          v-if="event.lot_type_cd"
          class="text-xs text-muted"
        >{{ event.lot_type_cd }}</span>
      </span>
    </div>

    <!-- AL_TEXT is the tool's own words for what failed. Two alids share the
         'meas' badge, so this line is what tells them apart — and it carries
         the alid so an unfamiliar message can be looked up. -->
    <p class="mt-1 sk-body text-(--sk-ink-muted)">
      <span class="font-mono text-xs">{{ event.alid }}</span>
      <span v-if="event.alarm_name">
        · {{ event.alarm_name }}
      </span>
      <span v-if="event.alarm_modelname">
        · {{ event.alarm_modelname }}
      </span>
    </p>

    <p
      v-if="details.length"
      class="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 sk-meta"
    >
      <span
        v-for="detail in details"
        :key="detail.label"
      >
        <span class="opacity-70">{{ detail.label }}</span> {{ detail.value }}
      </span>
    </p>
  </div>
</template>
