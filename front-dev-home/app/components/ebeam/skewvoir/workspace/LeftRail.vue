<template>
  <aside class="flex w-60 shrink-0 flex-col gap-5 overflow-y-auto border-r border-(--sk-border) bg-(--sk-surface) px-3 py-4">
    <!-- Back to search -->
    <button
      type="button"
      class="flex items-center gap-2 rounded-(--sk-r-nav) px-2.5 py-2 text-left text-[12.5px] font-medium text-zinc-600 transition-colors hover:bg-zinc-500/10 dark:text-zinc-300"
      @click="ws.goSearch()"
    >
      <UIcon
        name="i-lucide-arrow-left"
        class="h-4 w-4"
      />
      검색으로
    </button>

    <!-- View modes -->
    <section>
      <p class="mb-2 px-1 font-mono text-[10px] font-semibold tracking-wider text-(--sk-ink-muted)">
        WORKSPACE
      </p>
      <ul class="space-y-1">
        <li
          v-for="mode in ws.viewModes"
          :key="mode.kind"
        >
          <button
            type="button"
            class="flex w-full items-center gap-2.5 rounded-(--sk-r-nav) px-2.5 py-2 text-left transition-colors"
            :class="mode.kind === ws.activeKind.value
              ? 'bg-(--sk-ink) text-(--sk-ink-fg)'
              : 'text-zinc-600 hover:bg-zinc-500/10 dark:text-zinc-300'"
            @click="ws.openView(mode.kind)"
          >
            <span
              class="flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border"
              :class="mode.kind === ws.activeKind.value
                ? 'border-(--sk-ink-fg)/40 bg-(--sk-ink-fg)/15'
                : 'border-zinc-300 dark:border-zinc-600'"
            >
              <UIcon
                v-if="mode.kind === ws.activeKind.value"
                name="i-lucide-check"
                class="h-3 w-3"
              />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[12.5px] font-semibold">{{ mode.label }}</span>
              <span
                class="block truncate text-[10.5px]"
                :class="mode.kind === ws.activeKind.value ? 'text-(--sk-ink-fg)/70' : 'text-(--sk-ink-muted)'"
              >{{ mode.sub }}</span>
            </span>
            <UKbd
              :value="String(mode.index)"
              size="sm"
              :class="mode.kind === ws.activeKind.value ? 'opacity-80' : 'opacity-60'"
            />
          </button>
        </li>
      </ul>
    </section>

    <!-- Current selection -->
    <section
      v-if="ws.selection.value"
      class="space-y-1.5 border-t border-(--sk-border-soft) pt-4"
    >
      <p class="mb-1 px-1 font-mono text-[10px] font-semibold tracking-wider text-(--sk-ink-muted)">
        CURRENT SELECTION
      </p>
      <dl class="space-y-1 px-1 text-[11.5px]">
        <div
          v-for="field in selectionFields"
          :key="field.label"
          class="flex items-baseline justify-between gap-2"
        >
          <dt class="text-(--sk-ink-muted)">
            {{ field.label }}
          </dt>
          <dd
            class="truncate font-mono text-zinc-800 dark:text-zinc-200"
            :class="{ 'font-semibold': field.strong }"
          >
            {{ field.value }}
          </dd>
        </div>
      </dl>
    </section>

    <!-- Pinned filters -->
    <section class="space-y-2 border-t border-(--sk-border-soft) pt-4">
      <p class="px-1 font-mono text-[10px] font-semibold tracking-wider text-(--sk-ink-muted)">
        FILTER PINNED
      </p>
      <div class="space-y-1.5 px-1">
        <div
          v-for="field in filterFields"
          :key="field.label"
          class="flex items-center justify-between gap-2"
        >
          <span class="text-[11.5px] text-(--sk-ink-muted)">{{ field.label }}</span>
          <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 font-mono text-[11px] text-(--sk-chip-text)">
            {{ field.value }}
          </span>
        </div>
        <div class="flex flex-wrap gap-1.5 pt-1">
          <span
            v-for="flag in ws.pinnedFilters.value.flags"
            :key="flag"
            class="rounded-(--sk-r-chip) bg-(--sk-brand) px-2 py-0.5 font-mono text-[11px] font-medium text-(--sk-brand-fg)"
          >
            {{ flag }}
          </span>
          <button
            type="button"
            class="rounded-(--sk-r-chip) border border-dashed border-zinc-300 px-2 py-0.5 font-mono text-[11px] text-(--sk-ink-muted) hover:border-zinc-400 hover:text-(--sk-ink) dark:border-zinc-600"
          >
            + add
          </button>
        </div>
      </div>
    </section>

    <!-- Health -->
    <section class="mt-auto space-y-2 border-t border-(--sk-border-soft) pt-4">
      <p class="px-1 font-mono text-[10px] font-semibold tracking-wider text-(--sk-ink-muted)">
        HEALTH · LAST 31H
      </p>
      <div class="flex gap-6 px-1">
        <div>
          <p class="font-mono text-2xl font-bold tabular-nums text-zinc-900 dark:text-zinc-100">
            {{ ws.health.value.scans }}
          </p>
          <p class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            SCANS
          </p>
        </div>
        <div>
          <p class="font-mono text-2xl font-bold tabular-nums text-(--sk-bad)">
            {{ ws.health.value.outliers }}
          </p>
          <p class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            OUTLIERS
          </p>
        </div>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{ ws: SkewvoirWorkspace }>()

const selectionFields = computed(() => {
  const sel = props.ws.selection.value
  if (!sel) return []
  return [
    { label: 'Lot', value: sel.lot, strong: true },
    { label: 'Recipe', value: sel.recipe, strong: false },
    { label: 'EQ', value: sel.eq, strong: false },
    { label: 'MP', value: sel.mp, strong: false },
    { label: 'Captured', value: sel.capturedAt, strong: false }
  ]
})

const filterFields = computed(() => {
  const f = props.ws.pinnedFilters.value
  const sel = props.ws.selection.value
  return [
    { label: 'Area', value: f.area },
    { label: 'FAB', value: f.fab },
    { label: 'EQ type', value: f.eqType },
    { label: 'Period', value: f.period },
    { label: 'MP', value: sel?.mp ?? f.mp }
  ]
})
</script>
