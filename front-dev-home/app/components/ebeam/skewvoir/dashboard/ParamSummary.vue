<template>
  <EbeamSkewvoirPanelFrame
    title="파라미터 요약"
    :meta="summaries.length ? `${summaries.length}개` : undefined"
    icon="i-lucide-table"
    body-class="flex flex-col"
  >
    <div
      v-if="summaries.length"
      ref="scrollEl"
      tabindex="0"
      role="grid"
      class="min-h-0 flex-1 overflow-auto outline-none focus-visible:ring-1 focus-visible:ring-(--sk-brand)/40"
      @keydown="onKeydown"
    >
      <!-- Backend-computed stats (MsrParamSummary): the numbers come from the
           office pickle's full per-parameter population, not the rows the
           browser happens to hold — never recompute them client-side. -->
      <table class="w-full border-collapse text-xs">
        <thead class="sticky top-0 z-10 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border) font-mono text-[11px] text-(--sk-ink-muted)">
            <th
              scope="col"
              class="px-1.5 py-1.5 text-left font-semibold whitespace-nowrap"
            >
              파라미터
            </th>
            <th
              v-for="col in statColumns"
              :key="col"
              scope="col"
              class="px-1.5 py-1.5 text-right font-semibold whitespace-nowrap"
            >
              {{ col }}
            </th>
            <th
              scope="col"
              class="px-1.5 py-1.5 text-left font-semibold whitespace-nowrap"
            >
              Unit
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in summaries"
            :key="s.parameter"
            :data-row-key="s.parameter"
            :aria-selected="selectedSet.has(s.parameter)"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors duration-150 hover:bg-(--sk-chip-bg)"
            :class="s.parameter === activeParam
              ? 'bg-(--sk-chip-bg)'
              : selectedSet.has(s.parameter) ? 'bg-(--sk-brand)/10' : ''"
            @click="onRowClick(s.parameter, $event.metaKey || $event.ctrlKey || $event.shiftKey)"
          >
            <td
              class="px-1.5 py-1 font-mono whitespace-nowrap"
              :class="s.parameter === activeParam
                ? 'font-semibold text-(--sk-brand)'
                : selectedSet.has(s.parameter) ? 'font-medium text-(--sk-brand)' : 'text-(--sk-ink)'"
            >
              {{ s.parameter }}
            </td>
            <td class="px-1.5 py-1 text-right font-mono tabular-nums text-(--sk-ink)">
              {{ s.count }}
            </td>
            <td class="px-1.5 py-1 text-right font-mono tabular-nums text-(--sk-ink)">
              {{ fmt(s.mean) }}
            </td>
            <td class="px-1.5 py-1 text-right font-mono tabular-nums text-(--sk-ink-muted)">
              {{ fmt(s.std) }}
            </td>
            <td class="px-1.5 py-1 text-right font-mono tabular-nums text-(--sk-ink-muted)">
              {{ fmt(s.min) }}
            </td>
            <td class="px-1.5 py-1 text-right font-mono tabular-nums text-(--sk-ink-muted)">
              {{ fmt(s.max) }}
            </td>
            <td class="px-1.5 py-1 text-left text-(--sk-ink-muted)">
              {{ s.unit }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div
      v-else
      class="flex flex-1 items-center justify-center sk-body text-(--sk-ink-subtle)"
    >
      파라미터 없음
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { nextCursorIndex, type CursorKey } from '~/utils/tableCursor'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const statColumns = ['Count', 'Mean', 'Std', 'Min', 'Max']

const summaries = computed(() => props.analysis.paramSummaries.value)
const activeParam = computed(() => props.analysis.activeParam.value)
const selectedSet = computed(() => new Set(props.analysis.selectedParams.value))

// CD values are a few tens of nm — 2 decimals matches StatBar/Distribution.
const fmt = (v: number): string => (Number.isFinite(v) ? v.toFixed(2) : '—')

const scrollEl = ref<HTMLElement | null>(null)

const cursorIndex = computed(() =>
  summaries.value.findIndex(s => s.parameter === activeParam.value))

const focusRowAt = (index: number) => {
  const s = summaries.value[index]
  if (!s) return
  props.analysis.setParam(s.parameter) // move primary; extras (비교셋) preserved
  nextTick(() => {
    scrollEl.value
      ?.querySelector(`[data-row-key="${CSS.escape(s.parameter)}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  })
}

const onRowClick = (parameter: string, additive: boolean) => {
  props.analysis.toggleParam(parameter, additive)
  scrollEl.value?.focus()
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault()
    props.analysis.toggleParam(activeParam.value, true) // toggle comparison membership
    return
  }
  const nav = ['ArrowDown', 'ArrowUp', 'Home', 'End']
  if (!nav.includes(e.key)) return
  e.preventDefault()
  const next = nextCursorIndex(e.key as CursorKey, cursorIndex.value, summaries.value.length)
  if (next != null) focusRowAt(next)
}
</script>
