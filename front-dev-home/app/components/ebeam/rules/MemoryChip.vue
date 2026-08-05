<template>
  <span
    class="inline-flex h-5.5 items-center rounded-[var(--sk-r-sidebar)] border px-1.5 font-mono text-[11px] font-semibold tracking-wide"
    :class="chipClass"
  >{{ memory }}</span>
</template>

<script setup lang="ts">
// DRAM / NAND selector tag on a rule row. Extracted from Row + SampleTable,
// which carried two copies of the same markup.
//
// It used to be raw sky-* / amber-* utilities, which are outside the palette
// DESIGN.md declares complete. The distinction they carried is real — the
// memory class is what you scan the matrix by — so it is kept, re-encoded in
// the palette as TINT vs NEUTRAL rather than hue-A vs hue-B.
//
// Why that shape and not two tints: excluding the semantic families
// (--sk-ok/warn/bad — neither memory class is good or bad) and crimson
// (trim only), the system holds exactly one non-semantic tint, terracotta.
// So an in-palette binary has to be "tinted vs plain paper". DRAM takes the
// tint purely because the axis has to break somewhere; the pairing
// --sk-brand-soft + --sk-brand-ink is the documented readable-on-tint pair
// and inverts correctly under .dark. Both chips stay 11px/600 — the tint
// distinguishes them without implying one outranks the other.
const props = defineProps<{
  memory: 'DRAM' | 'NAND'
}>()

const chipClass = computed(() =>
  props.memory === 'DRAM'
    ? 'border-transparent bg-(--sk-brand-soft) text-(--sk-brand-ink)'
    : 'border-(--sk-border) bg-(--sk-muted-surface) text-(--sk-ink-muted)'
)
</script>
