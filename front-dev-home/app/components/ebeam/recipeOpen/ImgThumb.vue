<template>
  <div class="flex min-w-0 flex-col gap-1">
    <button
      type="button"
      class="relative mx-auto block aspect-square w-full max-w-[180px] cursor-zoom-in overflow-hidden rounded-md border border-zinc-300/70 bg-[#23201B] p-0 dark:border-zinc-700"
      :aria-label="`${imageSlot.label} 확대해서 보기`"
      @click="emit('open')"
    >
      <EbeamRecipeOpenSemNoise />
      <span
        class="absolute top-1 left-1 rounded-sm px-1.5 py-px font-mono text-[9px] font-bold tracking-wider"
        :class="isMeas
          ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
          : 'bg-(--sk-ink) text-(--sk-ink-fg)'"
      >{{ isMeas ? 'MEAS' : 'ADDR' }}</span>
      <span class="absolute right-1.5 bottom-1 font-mono text-[10px] text-white/55">⤢</span>
    </button>
    <div class="text-center font-mono text-[10.5px] font-semibold text-zinc-900 dark:text-zinc-100">
      {{ imageSlot.label }}
    </div>
    <div class="truncate text-center font-mono text-[9.5px] text-(--sk-ink-muted)">
      {{ filename }}
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ImageSlot } from '~/utils/recipeView'

const props = defineProps<{
  imageSlot: ImageSlot
  filename: string
}>()

const emit = defineEmits<{ (e: 'open'): void }>()

const isMeas = computed(() => props.imageSlot.role === 'measure')
</script>
