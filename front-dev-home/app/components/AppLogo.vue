<script setup lang="ts">
defineProps<{
  size?: 'sm' | 'md' | 'lg'
}>()
</script>

<template>
  <div class="flex items-center gap-3">
    <div class="flex items-center justify-center w-8 h-8 rounded-lg bg-zinc-900 dark:bg-zinc-100 text-zinc-100 dark:text-zinc-900 font-bold text-xs tracking-widest shadow-sm">
      SK
    </div>
    <span class="font-semibold text-lg tracking-tight text-zinc-900 dark:text-zinc-100">SKEWNONO</span>
  </div>
</template>
