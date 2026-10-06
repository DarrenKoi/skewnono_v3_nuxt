<template>
  <svg
    :viewBox="`0 0 ${W} ${H}`"
    preserveAspectRatio="none"
    class="h-8 w-full"
    aria-hidden="true"
  >
    <rect
      v-if="shape.band"
      x="0"
      :y="shape.band.y"
      :width="W"
      :height="shape.band.height"
      class="fill-(--sk-ink) opacity-[0.07]"
    />
    <path
      :d="shape.path"
      fill="none"
      class="stroke-(--sk-ink-muted)"
      stroke-width="1.4"
      vector-effect="non-scaling-stroke"
    />
    <circle
      v-for="dot in shape.dots"
      :key="dot.x"
      :cx="dot.x"
      :cy="dot.y"
      r="2.6"
      class="fill-(--sk-brand)"
    />
  </svg>
</template>

<script setup lang="ts">
// One tip's values as a line over its type's limits: the shaded band is
// "inside", a terracotta dot is a measurement outside it. A value the
// measurement did not record leaves a gap.
const props = defineProps<{
  values: (number | null)[]
  limits: { lcl: number, ucl: number } | null
}>()

const W = 150
const H = 32

const shape = computed(() => {
  const present = props.values.flatMap(v => v ?? [])
  const lo = Math.min(...present, props.limits?.lcl ?? Infinity)
  const hi = Math.max(...present, props.limits?.ucl ?? -Infinity)
  const span = hi - lo || 1
  const x = (i: number) => 4 + i * (W - 8) / Math.max(props.values.length - 1, 1)
  const y = (v: number) => H - 4 - (v - lo) * (H - 8) / span
  let pen = 'M'
  const path = props.values.map((v, i) => {
    if (v === null) {
      pen = 'M'
      return ''
    }
    const step = `${pen}${x(i).toFixed(1)},${y(v).toFixed(1)}`
    pen = 'L'
    return step
  }).join(' ')
  const { limits } = props
  return {
    path,
    band: limits && { y: y(limits.ucl), height: y(limits.lcl) - y(limits.ucl) },
    dots: props.values.flatMap((v, i) =>
      v !== null && limits && (v > limits.ucl || v < limits.lcl) ? [{ x: x(i), y: y(v) }] : [])
  }
})
</script>
