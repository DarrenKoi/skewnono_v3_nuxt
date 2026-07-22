<template>
  <div class="mt-3 flex flex-wrap items-center gap-2">
    <span class="sk-eyebrow">FILTERS</span>

    <EbeamSkewvoirSearchFacetSelect
      label="FAB"
      :options="facets.fab"
      :model-value="filters.fab"
      :disabled="disabled"
      @update:model-value="patch('fab', $event)"
    />
    <EbeamSkewvoirSearchFacetSelect
      label="장비 종류"
      :options="facets.model"
      :model-value="filters.model"
      :disabled="disabled"
      @update:model-value="patch('model', $event)"
    />
    <EbeamSkewvoirSearchFacetSelect
      label="EQ"
      :options="facets.eq"
      :model-value="filters.eq"
      :disabled="disabled"
      searchable
      @update:model-value="patch('eq', $event)"
    />

    <EbeamDateRangePopover
      v-if="anchor"
      :model-value="props.range"
      :anchor-date="anchor"
      :presets="periodPresets"
      @update:model-value="emit('set-date-range', $event)"
    />

    <UButton
      v-if="hasActive"
      color="neutral"
      variant="ghost"
      size="xs"
      icon="i-lucide-rotate-ccw"
      label="초기화"
      @click="emit('reset')"
    />
  </div>
</template>

<script setup lang="ts">
import type { MeasHistFacets } from '~/composables/useMeasHistApi'
import type { MeasHistFilters } from '~/composables/useMeasHistSearch'

const props = defineProps<{
  filters: MeasHistFilters
  facets: MeasHistFacets
  disabled?: boolean
  // Backend-declared clock. Presets resolve against it, not wall-clock today.
  anchor: string
  retentionDays: number
  // The composable's resolvedRange — the SAME from/to that goes into the
  // search request. A `date:` token in the search bar wins over this
  // dropdown, so the 기간 chip must render this resolved value rather than
  // deriving its own from `filters` alone, or the chip can show a range the
  // backend never received (see useMeasHistSearch's resolvedRange).
  range: { start: string, end: string }
}>()

const emit = defineEmits<{
  'update:filters': [value: MeasHistFilters]
  // A dropdown edit is "last write wins": the composable must both write
  // filters.from/to AND strip any date token out of queryText, or the two
  // inputs fight (see useMeasHistSearch's setDateRange doc comment). That
  // can't happen via a plain `update:filters` patch, so this gets its own
  // event instead of going through `patch()`.
  'set-date-range': [value: { start: string, end: string }]
  'reset': []
}>()

const patch = <K extends keyof MeasHistFilters>(key: K, value: MeasHistFilters[K]) => {
  emit('update:filters', { ...props.filters, [key]: value })
}

// Skewvoir search wants retention-aware presets (7/30/full window), unlike
// RecipeTatView/FailIssueView which use the shared Today/7/14/30 default —
// so this list is passed in locally rather than changing DateRangePopover's
// default for every consumer.
const periodPresets = computed(() => {
  const days = props.retentionDays > 0 ? props.retentionDays : 60
  return [
    { label: 'Last 7 days', days: 7 },
    { label: 'Last 30 days', days: 30 },
    { label: `Last ${days} days`, days }
  ]
})

const hasActive = computed(() =>
  props.filters.fab.length > 0
  || props.filters.model.length > 0
  || props.filters.eq.length > 0
  || Boolean(props.filters.from)
  || Boolean(props.filters.to)
)
</script>
