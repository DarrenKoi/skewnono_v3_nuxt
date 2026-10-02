<template>
  <span class="inline-flex h-[22px] shrink-0 items-center gap-1.5 rounded-(--sk-r-sidebar) border border-(--sk-border) bg-(--sk-surface) px-1.5">
    <span class="sk-eyebrow">Lot</span>
    <span class="sk-value-num font-semibold">{{ lotId }}</span>
  </span>
  <span
    v-if="slotNumber != null"
    class="inline-flex h-[22px] shrink-0 items-center gap-1.5 rounded-(--sk-r-sidebar) bg-(--sk-chip-bg) px-1.5"
  >
    <span class="sk-eyebrow">Slot</span>
    <span class="sk-value-num font-semibold">{{ slotNumber }}</span>
  </span>
</template>

<script setup lang="ts">
// The lot / slot pair as it appears in every AFM measurement list: each value
// carries the eyebrow that names it, and the two differ by container (outlined
// vs. recessed) so they read apart without the label. Two roots on purpose —
// the parent's own gap spaces them like its other children. 측정 상세 knows the
// slot only for a measurement opened from the list, so the slot tag is optional.
defineProps<{
  lotId: string
  slotNumber?: number | string | null
}>()
</script>
