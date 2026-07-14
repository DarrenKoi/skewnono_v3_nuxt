<template>
  <div class="mt-3 flex flex-wrap items-center gap-2">
    <span class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">FILTERS</span>

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
    <EbeamSkewvoirSearchFacetSelect
      label="RECIPE"
      :options="facets.recipe"
      :model-value="filters.recipe"
      :disabled="disabled"
      searchable
      @update:model-value="patch('recipe', $event)"
    />

    <EbeamDateRangePopover
      v-if="anchor"
      :model-value="props.range"
      :anchor-date="anchor"
      :presets="periodPresets"
      @update:model-value="setRange"
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
  'reset': []
}>()

const patch = <K extends keyof MeasHistFilters>(key: K, value: MeasHistFilters[K]) => {
  emit('update:filters', { ...props.filters, [key]: value })
}

// The 60-day mock retention window makes "Last 90 days" a lie — it can only
// return a clamped range. RecipeTatView/FailIssueView keep the shared
// Today/7/30/90 default (their own data isn't bound to this 60-day window),
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

const setRange = (value: { start: string, end: string }) => {
  emit('update:filters', { ...props.filters, from: value.start, to: value.end })
}

const hasActive = computed(() =>
  props.filters.fab.length > 0
  || props.filters.model.length > 0
  || props.filters.eq.length > 0
  || props.filters.recipe.length > 0
  || Boolean(props.filters.from)
  || Boolean(props.filters.to)
)
</script>
