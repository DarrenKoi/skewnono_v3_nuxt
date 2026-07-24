<template>
  <EbeamSkewvoirPanelFrame
    title="파라미터 요약"
    :meta="summaries.length ? `${summaries.length}개` : undefined"
    icon="i-lucide-table"
    body-class="flex flex-col"
  >
    <div
      v-if="summaries.length"
      class="min-h-0 flex-1 overflow-auto"
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
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors duration-150 hover:bg-(--sk-chip-bg)"
            :class="s.parameter === activeParam ? 'bg-(--sk-chip-bg)' : ''"
            @click="analysis.setParam(s.parameter)"
          >
            <td
              class="px-1.5 py-1 font-mono whitespace-nowrap"
              :class="s.parameter === activeParam ? 'font-semibold text-(--sk-brand)' : 'text-(--sk-ink)'"
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

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const statColumns = ['Count', 'Mean', 'Std', 'Min', 'Max']

const summaries = computed(() => props.analysis.paramSummaries.value)
const activeParam = computed(() => props.analysis.activeParam.value)

// CD values are a few tens of nm — 2 decimals matches StatBar/Distribution.
const fmt = (v: number): string => (Number.isFinite(v) ? v.toFixed(2) : '—')
</script>
