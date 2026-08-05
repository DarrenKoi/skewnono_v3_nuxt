<template>
  <span
    class="inline-flex h-7 min-w-12 items-center justify-center rounded-[var(--sk-r-chip)] border px-2 font-mono text-[13px] tabular-nums"
    :class="cellClass"
    :title="title"
  >
    {{ display }}
  </span>
</template>

<script setup lang="ts">
// Read-only cap display (D13). Step 3 adds inline editing; step 4 adds the
// monitor color overlay. For now it renders the cap integer faithfully:
//   undefined → "—" (type not applicable to this cell)
//   0         → measurement forbidden (EDGE_EX 0)
//   n         → upper bound
// emphasis marks caps opened up beyond the EV baseline (TV 포함 이후 · 수율 후);
// it only tints positive caps — 0/— keep their own meaning.
//
// A cap is a data value, so DESIGN.md's "values are ink" rule holds in every
// state: the digit never drops below --sk-ink-muted. State rides on weight,
// border and fill instead — which is also why emphasis uses crimson purely as
// trim (border + tint) and never as the digit's colour.
const props = defineProps<{
  value: number | undefined
  emphasis?: boolean
}>()

const isNA = computed(() => props.value === undefined)
const isZero = computed(() => props.value === 0)

const display = computed(() => (isNA.value ? '—' : String(props.value)))

const title = computed(() => {
  if (isNA.value) return '해당 없음'
  if (isZero.value) return '측정 금지 (cap 0)'
  if (props.emphasis) return `상한 ${props.value} (≤) · EV 룰 대비 확대`
  return `상한 ${props.value} (≤)`
})

const cellClass = computed(() => {
  // "—" is the one state that is not a value, so ink-subtle is correct here.
  if (isNA.value) {
    return 'border-dashed border-(--sk-border) bg-transparent font-medium text-(--sk-ink-subtle)'
  }
  // 0 = 측정 금지. Recessive through the muted fill, still legible at ink-muted.
  if (isZero.value) {
    return 'border-(--sk-border) bg-(--sk-muted-surface) font-semibold text-(--sk-ink-muted)'
  }
  if (props.emphasis) {
    return 'border-(--sk-accent-border) bg-(--sk-accent-tint) font-bold text-(--sk-ink)'
  }
  return 'border-(--sk-border) bg-(--sk-surface) font-semibold text-(--sk-ink)'
})
</script>
