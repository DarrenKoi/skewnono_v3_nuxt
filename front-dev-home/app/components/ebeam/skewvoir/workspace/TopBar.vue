<template>
  <div class="flex items-center gap-3 border-b border-(--sk-border) bg-(--sk-surface) px-3 py-2">
    <!-- Brand -->
    <div class="flex items-center gap-2 pr-1">
      <span class="flex h-7 w-7 items-center justify-center rounded-(--sk-r-chip) bg-(--sk-ink) font-mono text-sm font-bold text-(--sk-ink-fg)">
        S
      </span>
      <div class="leading-none">
        <p class="text-[13px] font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          SKEWNONO<span class="text-(--sk-brand)">.</span>
        </p>
        <p class="mt-0.5 font-mono text-[9.5px] text-zinc-400">
          {{ version }} · {{ ws.toolLabel }}
        </p>
      </div>
    </div>

    <!-- Active selection summary -->
    <div class="flex min-w-0 flex-1 items-center gap-2">
      <template v-if="ws.selection.value">
        <span class="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-(--sk-r-nav) bg-(--sk-ink) px-2.5 text-[12px] font-medium text-(--sk-ink-fg)">
          <UIcon
            name="i-lucide-microscope"
            class="h-3.5 w-3.5 opacity-70"
          />
          <span class="max-w-[12rem] truncate">{{ ws.selection.value.lot }}</span>
        </span>
        <span class="truncate font-mono text-[11px] text-(--sk-ink-muted)">
          {{ ws.selection.value.recipe }} · {{ ws.selection.value.eq }}
        </span>
      </template>
      <span
        v-else
        class="font-mono text-[11px] text-(--sk-ink-subtle)"
      >
        측정 미선택
      </span>
    </div>

    <!-- Right meta -->
    <div class="flex items-center gap-2.5 pl-1">
      <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ dataPath }}</span>
      <span class="flex h-6 w-6 items-center justify-center rounded-(--sk-r-chip) bg-zinc-900 font-mono text-[10px] font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
        {{ user }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{ ws: SkewvoirWorkspace }>()

const version = 'v0.7.1'
const user = 'KSH'

const dataPath = computed(() => {
  const sel = props.ws.selection.value
  const fab = props.ws.pinnedFilters.value.fab.toLowerCase()
  return sel ? `/data/${fab}/${sel.eq}` : `/data/${fab}`
})
</script>
