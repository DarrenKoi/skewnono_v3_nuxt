<template>
  <span
    class="inline-flex h-5.5 items-center rounded-[var(--sk-r-sidebar)] border border-(--sk-border) bg-(--sk-muted-surface) px-1.5 font-mono text-[11px] font-semibold tracking-wide text-(--sk-ink-muted)"
  >{{ memory }}</span>
</template>

<script setup lang="ts">
// DRAM / NAND selector tag on a rule row. Extracted from Row + SampleTable,
// which carried two copies of the same markup.
//
// It used to be raw sky-* / amber-* utilities. Those are outside the palette
// DESIGN.md declares complete (paper · walnut · ink · terracotta · crimson
// trim), and hue was doing work two distinct four-letter words already do —
// so the chip is now neutral and merely 11px rather than 10px, which is the
// micro-label floor for chrome that names a row.
defineProps<{
  memory: 'DRAM' | 'NAND'
}>()
</script>
