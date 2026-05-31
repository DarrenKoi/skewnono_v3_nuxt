<template>
  <span
    class="inline-flex h-7 min-w-11 items-center justify-center rounded-md border px-2 font-mono text-[13px] font-semibold tabular-nums"
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
const props = defineProps<{
  value: number | undefined
}>()

const isNA = computed(() => props.value === undefined)
const isZero = computed(() => props.value === 0)

const display = computed(() => (isNA.value ? '—' : String(props.value)))

const title = computed(() => {
  if (isNA.value) return '해당 없음'
  if (isZero.value) return '측정 금지 (cap 0)'
  return `상한 ${props.value} (≤)`
})

const cellClass = computed(() => {
  if (isNA.value) {
    return 'border-dashed border-(--sk-border) bg-transparent text-(--sk-ink-subtle)'
  }
  if (isZero.value) {
    return 'border-(--sk-border) bg-(--sk-surface) text-(--sk-ink-subtle)'
  }
  return 'border-(--sk-border) bg-(--sk-surface) text-(--sk-ink)'
})
</script>
