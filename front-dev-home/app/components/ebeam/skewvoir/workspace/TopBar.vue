<template>
  <div class="flex items-stretch gap-3 border-b border-(--sk-border) bg-(--sk-surface) px-3 py-2">
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

    <!-- Tabs -->
    <div class="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
      <button
        v-for="(tab, index) in ws.tabs.value"
        :key="tab.id"
        type="button"
        class="group inline-flex h-7 shrink-0 items-center gap-1.5 rounded-(--sk-r-nav) px-2.5 text-[12px] font-medium transition-colors"
        :class="tab.id === ws.activeTabId.value
          ? 'bg-(--sk-ink) text-(--sk-ink-fg)'
          : 'text-zinc-500 hover:bg-zinc-500/10 dark:text-zinc-400'"
        @click="ws.activate(tab.id)"
      >
        <span class="font-mono text-[10px] opacity-60">{{ index + 1 }}</span>
        <span class="max-w-[12rem] truncate">{{ tab.label }}</span>
        <span
          v-if="tab.badge"
          class="rounded-(--sk-r-chip) bg-(--sk-brand) px-1.5 py-px font-mono text-[9px] font-semibold text-(--sk-brand-fg)"
        >
          {{ tab.badge }}
        </span>
        <UIcon
          v-if="tab.closable"
          name="i-lucide-x"
          class="h-3 w-3 opacity-40 transition-opacity hover:opacity-100"
          @click.stop="ws.closeTab(tab.id)"
        />
      </button>

      <button
        type="button"
        class="inline-flex h-7 shrink-0 items-center gap-1 rounded-(--sk-r-nav) px-2 text-[12px] font-medium text-zinc-400 hover:bg-zinc-500/10 hover:text-zinc-600 dark:hover:text-zinc-200"
        @click="ws.newTab()"
      >
        <UIcon
          name="i-lucide-plus"
          class="h-3.5 w-3.5"
        />
        New
      </button>
    </div>

    <!-- Right meta -->
    <div class="flex items-center gap-2.5 pl-1">
      <span class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) bg-(--sk-ok-soft) px-2 py-1 text-[10.5px] font-medium text-(--sk-ok)">
        <span class="h-1.5 w-1.5 rounded-full bg-(--sk-ok)" />
        {{ streamCount }} streams
      </span>
      <span class="font-mono text-[11px] text-zinc-500">{{ dataPath }}</span>
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

const streamCount = computed(() => props.ws.tabs.value.filter(tab => tab.closable).length)

const dataPath = computed(() => {
  const sel = props.ws.selection.value
  const fab = props.ws.pinnedFilters.value.fab.toLowerCase()
  return sel ? `/data/${fab}/${sel.eq}` : `/data/${fab}`
})
</script>
