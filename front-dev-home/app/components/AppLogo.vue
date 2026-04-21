<script setup lang="ts">
defineProps<{
  size?: 'sm' | 'md' | 'lg'
}>()
</script>

<template>
  <div class="flex items-center gap-3">
    <div class="flex items-center justify-center w-9 h-9 rounded-full bg-zinc-900 dark:bg-zinc-100 text-zinc-100 dark:text-zinc-900 font-bold text-[10px] tracking-widest">
      SK
    </div>
    <span class="font-semibold text-lg tracking-tight text-zinc-900 dark:text-zinc-100">SKEWNONO</span>
  </div>
</template>
