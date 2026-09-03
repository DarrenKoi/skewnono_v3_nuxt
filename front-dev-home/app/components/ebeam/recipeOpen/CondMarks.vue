<template>
  <!-- Sits in the same box as the <img>. The viewBox is the loaded image's
       natural size (the cond Pixel size until it loads) and preserveAspectRatio
       mirrors the image's object-fit (`meet` = contain, `slice` = cover), so
       the SVG lands exactly where the browser put the picture, at any size —
       and the marks, being FRACTIONS, stay put on a copy the tool saved at a
       different resolution. Strokes are non-scaling so a hairline stays a
       hairline. Each mark is drawn twice — a dark halo under the colour — so
       it reads on a white-saturated micrograph too. -->
  <svg
    v-if="marks"
    class="pointer-events-none absolute inset-0 h-full w-full"
    :viewBox="`0 0 ${size[0]} ${size[1]}`"
    :preserveAspectRatio="fit === 'cover' ? 'xMidYMid slice' : 'xMidYMid meet'"
    aria-hidden="true"
  >
    <template v-if="marks.box">
      <rect
        v-for="pass in passes"
        :key="`box-${pass.k}`"
        :x="marks.box[0] * size[0]"
        :y="marks.box[1] * size[1]"
        :width="(marks.box[2] - marks.box[0]) * size[0]"
        :height="(marks.box[3] - marks.box[1]) * size[1]"
        fill="none"
        :stroke="pass.k === 'halo' ? HALO : 'var(--sk-warn)'"
        :stroke-width="pass.w"
        vector-effect="non-scaling-stroke"
      />
    </template>
    <template v-if="marks.crosshair">
      <template
        v-for="pass in passes"
        :key="`cross-${pass.k}`"
      >
        <line
          :x1="cx"
          y1="0"
          :x2="cx"
          :y2="size[1]"
          :stroke="pass.k === 'halo' ? HALO : 'var(--sk-ok)'"
          :stroke-width="pass.w"
          vector-effect="non-scaling-stroke"
        />
        <line
          x1="0"
          :y1="cy"
          :x2="size[0]"
          :y2="cy"
          :stroke="pass.k === 'halo' ? HALO : 'var(--sk-ok)'"
          :stroke-width="pass.w"
          vector-effect="non-scaling-stroke"
        />
        <circle
          :cx="cx"
          :cy="cy"
          :r="size[0] / 40"
          fill="none"
          :stroke="pass.k === 'halo' ? HALO : 'var(--sk-ok)'"
          :stroke-width="pass.w"
          vector-effect="non-scaling-stroke"
        />
      </template>
    </template>
  </svg>
</template>

<script setup lang="ts">
/**
 * The tool's marks over a recipe image: the crosshair where its algorithm
 * placed the align / measurement point, and the white box the recipe drew
 * around its unique area — both read from the image's cond.txt rows.
 */
import { condMarks, type CondRowLike } from '~/utils/condCrosshair'

const props = withDefaults(defineProps<{
  rows: readonly CondRowLike[] | null | undefined
  /** The `object-fit` of the <img> this overlays. */
  fit?: 'contain' | 'cover'
  /** The <img>'s naturalWidth/naturalHeight once loaded. */
  natural?: [number, number] | null
}>(), { fit: 'contain', natural: null })

const HALO = 'rgb(0 0 0 / 0.55)'
const passes = [{ k: 'halo', w: 3 }, { k: 'ink', w: 1.5 }] as const

const marks = computed(() => condMarks(props.rows))
const size = computed<[number, number]>(() =>
  props.natural && props.natural[0] > 0 && props.natural[1] > 0
    ? props.natural
    : marks.value?.pixel ?? [1, 1])
const cx = computed(() => (marks.value?.crosshair?.[0] ?? 0) * size.value[0])
const cy = computed(() => (marks.value?.crosshair?.[1] ?? 0) * size.value[1])
</script>
