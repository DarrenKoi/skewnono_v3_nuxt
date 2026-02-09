<script setup lang="ts">
defineProps<{
  size?: 'sm' | 'md' | 'lg'
}>()
</script>

<template>
  <div class="flex items-center gap-2">
    <div class="flex items-center justify-center w-8 h-8 rounded-lg bg-primary-500 text-white font-bold text-sm">
      SK
    </div>
    <span class="font-semibold text-lg tracking-tight">SKEWNONO</span>
  </div>
</template>
