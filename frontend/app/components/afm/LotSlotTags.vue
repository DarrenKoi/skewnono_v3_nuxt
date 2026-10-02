<template>
  <span class="inline-flex h-[22px] shrink-0 items-center gap-1.5 rounded-(--sk-r-sidebar) border border-(--sk-border) bg-(--sk-surface) px-1.5">
    <span class="sk-eyebrow">Lot</span>
    <span class="sk-value-num font-semibold">{{ lotId }}</span>
  </span>
  <span class="inline-flex h-[22px] shrink-0 items-center gap-1.5 rounded-(--sk-r-sidebar) bg-(--sk-chip-bg) px-1.5">
    <span class="sk-eyebrow">Slot</span>
    <span class="sk-value-num font-semibold">{{ slotNumber }}</span>
  </span>
</template>

<script setup lang="ts">
// The lot / slot pair as it appears in every AFM measurement list: each value
// carries the eyebrow that names it, and the two differ by container (outlined
// vs. recessed) so they read apart without the label. Two roots on purpose —
// the parent's own gap spaces them like its other children.
defineProps<{
  lotId: string
  slotNumber: number | string
}>()
</script>
