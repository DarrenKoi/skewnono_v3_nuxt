<template>
  <div class="dashboard-surface flex flex-wrap items-center gap-1.5 rounded-2xl px-3.5 py-2.5">
    <span class="font-mono text-[10px] text-(--sk-ink-muted)">
      {{ text.label }}
    </span>
    <button
      v-for="lot in lotCds"
      :key="lot"
      type="button"
      class="group inline-flex h-7 items-center gap-1.5 rounded-md bg-white px-2.5 font-mono text-[12px] text-zinc-700 ring-1 ring-zinc-200 transition-colors hover:bg-zinc-50 hover:text-zinc-950 hover:ring-(--sk-accent) dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-50"
      :aria-label="`${lot} ${text.aria}`"
      @click="emit('select', lot)"
    >
      <span>{{ lot }}</span>
      <UIcon
        name="i-lucide-arrow-up-right"
        class="h-3.5 w-3.5 text-(--sk-ink-muted) transition-colors group-hover:text-(--sk-accent)"
      />
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  lotCds: string[]
}>()

const emit = defineEmits<{
  select: [lotCd: string]
}>()

const text = {
  label: 'detail',
  aria: '레시피 상세 보기'
} as const
</script>
