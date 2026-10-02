<template>
  <div class="min-w-0 flex-1 space-y-1">
    <p class="flex items-baseline gap-2">
      <span class="shrink-0 font-mono text-xs tabular-nums text-(--sk-ink-muted)">
        {{ item.formattedDate }}
      </span>
      <span class="truncate text-sm font-semibold text-(--sk-ink)">
        {{ item.recipeName }}
      </span>
    </p>
    <p class="flex flex-wrap items-center gap-x-2 gap-y-1">
      <AfmLotSlotTags
        :lot-id="item.lotId"
        :slot-number="item.slotNumber"
      />
      <slot />
    </p>
  </div>
</template>

<script setup lang="ts">
import type { AfmMeasurement } from '~/composables/useAfmCart'

// One measurement as the side cards list it: date and recipe on the first
// line, lot / slot tags on the second. The slot holds whatever the card adds
// after the tags (when it was viewed, the measurement badge).
defineProps<{
  item: AfmMeasurement
}>()
</script>
