<template>
  <button
    type="button"
    class="ml-auto shrink-0 rounded-(--sk-r-sidebar) sk-label transition-colors duration-200 hover:text-(--sk-ink)"
    :aria-expanded="expanded"
    @click="$emit('toggle')"
  >
    자세히
  </button>
</template>

<script setup lang="ts">
// The 자세히 disclosure on a 측정 개요 verdict column. One component rather than
// the same eight lines in each of the three columns — the next column added gets
// the geometry, the hover and the aria state for free instead of by copy.
defineProps<{ expanded: boolean }>()
defineEmits<{ (e: 'toggle'): void }>()
</script>
