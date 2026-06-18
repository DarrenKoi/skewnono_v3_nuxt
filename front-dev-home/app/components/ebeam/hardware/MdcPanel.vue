<template>
  <div class="mt-3 space-y-3">
    <div
      v-if="matrix.tools.length === 0"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
    >
      MDC 설정 데이터가 없습니다.
    </div>
    <div
      v-else
      class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
    >
      <table class="min-w-full text-left text-xs">
        <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
          <tr>
            <th class="whitespace-nowrap px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">
              EQP
            </th>
            <th
              v-for="cond in matrix.conditions"
              :key="cond"
              class="whitespace-nowrap px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]"
            >
              {{ cond }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(tool, row) in matrix.tools"
            :key="tool"
            class="border-t border-(--sk-border-soft)"
            :class="row === 0 ? 'bg-(--sk-muted-surface)' : ''"
          >
            <td class="whitespace-nowrap px-3 py-2 font-mono font-bold text-(--sk-ink)">
              {{ tool }}
              <span
                v-if="row === 0"
                class="ml-1 rounded bg-(--sk-ink) px-1 text-[9px] text-white dark:text-zinc-900"
              >선택</span>
            </td>
            <td
              v-for="(cond, col) in matrix.conditions"
              :key="cond"
              class="whitespace-nowrap px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink)"
              :style="cellStyle(row, col)"
            >
              {{ formatCell(matrix.values[row]?.[col]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { buildMdcMatrix, cellDeviation } from '~/utils/mdcMatrix'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  selectedEqp: string
}>()

const matrix = computed(() => buildMdcMatrix(props.settings, props.selectedEqp))

const formatCell = (v: number | null | undefined) =>
  v === null || v === undefined ? '-' : v.toFixed(4)

// Warm (rose) for above-baseline, cool (sky) for below; alpha = magnitude.
const cellStyle = (row: number, col: number) => {
  if (row === 0) return {}
  const dev = cellDeviation(matrix.value, row, col)
  if (dev === 0) return {}
  const alpha = Math.min(Math.abs(dev) * 0.6, 0.6).toFixed(3)
  const rgb = dev > 0 ? '244, 63, 94' : '56, 189, 248'
  return { backgroundColor: `rgba(${rgb}, ${alpha})` }
}
</script>
