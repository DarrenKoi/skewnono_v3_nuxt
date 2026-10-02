<template>
  <span class="flex min-w-0 flex-col gap-1.5">
    <span
      class="truncate text-sm font-semibold text-(--sk-ink)"
      :title="measurement.recipeName"
    >
      {{ measurement.recipeName }}
    </span>
    <span class="flex flex-wrap items-center gap-x-2 gap-y-1.5">
      <span class="font-mono text-[13px] tabular-nums text-(--sk-ink)">
        {{ measurement.formattedDate }}
      </span>
      <AfmLotSlotTags
        :lot-id="measurement.lotId"
        :slot-number="measurement.slotNumber"
      />
      <span class="sk-badge shrink-0 border border-(--sk-border-soft) bg-(--sk-muted-surface) px-2 font-sans font-medium text-(--sk-ink)">
        {{ measurement.measuredInfo }}
      </span>
      <slot />
    </span>
  </span>
</template>

<script setup lang="ts">
// One measurement as the AFM side lists show it, where there is no column header:
// the recipe is the headline, and date / lot / slot / 측정 sit on one line under
// it. The search results use columns instead (SearchBar.vue), because there the
// header names each value once.
import type { AfmMeasurement } from '~/composables/useAfmCart'

defineProps<{
  measurement: AfmMeasurement
}>()
</script>
