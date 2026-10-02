<template>
  <span class="sk-badge shrink-0 gap-1.5 border border-(--sk-border) bg-(--sk-surface) px-2 text-(--sk-ink)">
    <span class="font-sans text-xs font-medium text-(--sk-ink-muted)">Lot</span>
    {{ lotId }}
  </span>
  <span class="sk-badge shrink-0 gap-1.5 bg-(--sk-chip-bg) px-2 text-(--sk-ink)">
    <span class="font-sans text-xs font-medium text-(--sk-ink-muted)">Slot</span>
    {{ slotNumber }}
  </span>
</template>

<script setup lang="ts">
// The lot / slot pair as it appears in the AFM lists that have no column header
// (조회 기록, 데이터 그룹, 시계열 비교): each value carries the label that names
// it, and the two differ by container (outlined vs. recessed) so they read apart
// without the label. `.sk-badge` geometry — 24px, mono 13px — because these are
// values the reader matches by eye, not chrome. Two roots on purpose: the
// parent's own gap spaces them like its other children.
defineProps<{
  lotId: string
  slotNumber: number | string
}>()
</script>
