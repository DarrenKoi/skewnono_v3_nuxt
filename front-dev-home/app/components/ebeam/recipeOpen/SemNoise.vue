<template>
  <div
    aria-hidden="true"
    class="sem-noise pointer-events-none absolute inset-0"
  />
</template>

<script setup lang="ts">
</script>

<style scoped>
.sem-noise {
  background:
    repeating-linear-gradient(45deg, rgba(255, 255, 255, 0.04) 0 2px, transparent 2px 5px),
    repeating-linear-gradient(-30deg, rgba(0, 0, 0, 0.18) 0 1px, transparent 1px 3px),
    radial-gradient(ellipse at 30% 40%, rgba(255, 255, 255, 0.07), transparent 60%),
    radial-gradient(ellipse at 70% 70%, rgba(255, 255, 255, 0.05), transparent 55%);
}
</style>
