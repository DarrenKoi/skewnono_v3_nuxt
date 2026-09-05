<template>
  <!-- Sits in the same box as the <img>. The viewBox is the cond Pixel size
       and preserveAspectRatio mirrors the image's object-fit (`meet` =
       contain, `slice` = cover), so the SVG lands exactly where the browser
       put the picture at any size — and because the marks are FRACTIONS, a
       copy saved at another resolution still lands on the same feature.
       Strokes are non-scaling so a hairline stays a hairline; the drop
       shadow is the halo that keeps them readable on a white micrograph. -->
  <svg
    v-if="marks"
    class="pointer-events-none absolute inset-0 h-full w-full"
    :viewBox="`0 0 ${w} ${h}`"
    :preserveAspectRatio="fit === 'cover' ? 'xMidYMid slice' : 'xMidYMid meet'"
    aria-hidden="true"
  >
    <g
      fill="none"
      stroke-width="1.5"
      style="filter: drop-shadow(0 0 1.5px rgb(0 0 0 / 0.7))"
    >
      <template v-if="marks.box">
        <!-- The offset: white-box centre (warn) to the image centre (accent),
             which is the recipe's actual align point. -->
        <line
          :x1="boxCx"
          :y1="boxCy"
          :x2="w / 2"
          :y2="h / 2"
          stroke="var(--sk-accent)"
          stroke-dasharray="4 3"
          vector-effect="non-scaling-stroke"
        />
        <circle
          :cx="boxCx"
          :cy="boxCy"
          :r="boxPointRadius"
          fill="var(--sk-warn)"
          stroke="var(--sk-warn)"
          vector-effect="non-scaling-stroke"
        />
        <line
          :x1="w / 2"
          :y1="h / 2 - alignArm"
          :x2="w / 2"
          :y2="h / 2 + alignArm"
          stroke="var(--sk-accent)"
          vector-effect="non-scaling-stroke"
        />
        <line
          :x1="w / 2 - alignArm"
          :y1="h / 2"
          :x2="w / 2 + alignArm"
          :y2="h / 2"
          stroke="var(--sk-accent)"
          vector-effect="non-scaling-stroke"
        />
        <circle
          :cx="w / 2"
          :cy="h / 2"
          :r="boxPointRadius"
          fill="var(--sk-accent)"
          stroke="var(--sk-accent)"
          vector-effect="non-scaling-stroke"
        />
      </template>
      <template v-if="marks.crosshair">
        <line
          :x1="cx"
          y1="0"
          :x2="cx"
          :y2="h"
          stroke="var(--sk-ok)"
          vector-effect="non-scaling-stroke"
        />
        <line
          x1="0"
          :y1="cy"
          :x2="w"
          :y2="cy"
          stroke="var(--sk-ok)"
          vector-effect="non-scaling-stroke"
        />
        <circle
          :cx="cx"
          :cy="cy"
          :r="w / 40"
          stroke="var(--sk-ok)"
          vector-effect="non-scaling-stroke"
        />
      </template>
    </g>
  </svg>
</template>

<script setup lang="ts">
/**
 * The tool's marks over a recipe image: the crosshair where its algorithm
 * placed the measurement point, and — when the recipe drew a white box around
 * its unique area — the box centre AND the image centre, joined by a dashed
 * offset line. The image centre is the recipe's actual align point; the box
 * centre is only the matching cue, and the two differ by exactly the offset
 * auto_recipe_creator adds to its click (docs/align_point_from_cond.md there).
 * `marks` comes parsed from the server (fractions of the image) — see
 * back_dev_home/_core/cond_cursor.py.
 */
import type { CursorMarks } from '~/composables/useRecipeParamDetail'

const props = withDefaults(defineProps<{
  marks: CursorMarks | null | undefined
  /** The `object-fit` of the <img> this overlays. */
  fit?: 'contain' | 'cover'
}>(), { fit: 'contain' })

const w = computed(() => props.marks?.pixel[0] ?? 1)
const h = computed(() => props.marks?.pixel[1] ?? 1)
const cx = computed(() => (props.marks?.crosshair?.[0] ?? 0) * w.value)
const cy = computed(() => (props.marks?.crosshair?.[1] ?? 0) * h.value)
const boxCx = computed(() => ((props.marks?.box?.[0] ?? 0) + (props.marks?.box?.[2] ?? 0)) / 2 * w.value)
const boxCy = computed(() => ((props.marks?.box?.[1] ?? 0) + (props.marks?.box?.[3] ?? 0)) / 2 * h.value)
const boxPointRadius = computed(() => Math.min(w.value, h.value) / 160)
// Half-length of the image-centre cross arms, in viewBox units.
const alignArm = computed(() => Math.min(w.value, h.value) / 32)
</script>
