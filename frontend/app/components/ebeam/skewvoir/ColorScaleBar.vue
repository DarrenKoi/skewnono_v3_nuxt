<template>
  <!-- Dumb, reusable color-scale legend: gradient + min/mid/max ticks + unit.
       Lives in the DOM (never inside the wafer square) so it can't overlap the
       inscribed circle. Shared by the panel and the detail modal. -->
  <div class="flex w-full flex-col items-center gap-0.5">
    <div
      class="h-2.5 w-full max-w-[16rem] rounded-(--sk-r-sidebar)"
      :style="gradientStyle"
    />
    <div class="flex w-full max-w-[16rem] items-center justify-between font-mono text-xs tabular-nums text-(--sk-ink-muted)">
      <span class="text-(--sk-ink)">{{ label(min) }}</span>
      <span>{{ label((min + max) / 2) }}</span>
      <span class="text-(--sk-ink)">{{ label(max) }} {{ unit }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { SK_SCALE } from '~/utils/chartPalette'
import { scaleFormatter } from '~/utils/scaleLabel'

const props = withDefaults(defineProps<{
  min: number
  max: number
  unit: string
  colors?: string[]
}>(), {
  colors: () => [...SK_SCALE]
})

// One formatter for min · mid · max, so the two ends never print alike.
const label = computed(() => scaleFormatter(props.min, props.max))

const gradientStyle = computed(() => ({
  background: `linear-gradient(to right, ${props.colors.join(', ')})`
}))
</script>
