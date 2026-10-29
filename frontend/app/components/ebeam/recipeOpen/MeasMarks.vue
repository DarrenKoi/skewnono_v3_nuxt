<template>
  <!-- Same box-over-<img> contract as CondMarks: viewBox = Pixel, aspect
       mirrors object-fit, strokes non-scaling. -->
  <svg
    v-if="meas"
    class="pointer-events-none absolute inset-0 h-full w-full"
    :viewBox="`0 0 ${w} ${h}`"
    :preserveAspectRatio="fit === 'cover' ? 'xMidYMid slice' : 'xMidYMid meet'"
    aria-hidden="true"
  >
    <g
      fill="none"
      stroke="var(--sk-brand)"
      stroke-width="1.5"
      style="filter: drop-shadow(0 0 1.5px rgb(0 0 0 / 0.7))"
    >
      <rect
        v-for="([cx, cy, bw, bh], i) in meas.bars"
        :key="`b${i}`"
        :x="(cx - bw / 2) * w"
        :y="(cy - bh / 2) * h"
        :width="bw * w"
        :height="bh * h"
        vector-effect="non-scaling-stroke"
      />
      <template
        v-for="([cx, cy, rIn, rOut], i) in meas.circles"
        :key="`c${i}`"
      >
        <circle
          :cx="cx * w"
          :cy="cy * h"
          :r="rIn * w"
          vector-effect="non-scaling-stroke"
        />
        <circle
          v-if="rOut > 0"
          :cx="cx * w"
          :cy="cy * h"
          :r="rOut * w"
          stroke-dasharray="4 3"
          vector-effect="non-scaling-stroke"
        />
      </template>
    </g>
  </svg>
</template>

<script setup lang="ts">
/**
 * Where the parameter measures on its image: AMP-derived boxes and circles
 * (backend: office_utils.meas_marks). Fractions of the image; radii are
 * fractions of the WIDTH.
 */
import type { MeasMarks } from '~/composables/useRecipeParamDetail'

const props = withDefaults(defineProps<{
  meas: MeasMarks | null | undefined
  /** The `object-fit` of the <img> this overlays. */
  fit?: 'contain' | 'cover'
}>(), { fit: 'contain' })

const w = computed(() => props.meas?.pixel[0] ?? 1)
const h = computed(() => props.meas?.pixel[1] ?? 1)
</script>
