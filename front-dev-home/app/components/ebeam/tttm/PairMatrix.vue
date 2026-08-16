<template>
  <div class="dashboard-surface rounded-2xl p-5 space-y-5">
    <p class="text-xs text-(--sk-ink-subtle)">
      장비쌍 스큐 행렬 (TTTM 근거 · 셀별)
    </p>

    <div
      v-for="cell in cells"
      :key="cell.cell_id"
      class="space-y-2"
    >
      <div class="flex items-center gap-2 text-sm">
        <span class="font-medium text-(--sk-ink)">{{ cell.beam_condition }} · {{ cell.axis }} · {{ cell.cd_band }}nm</span>
        <span
          class="px-1.5 py-0.5 rounded text-xs"
          :style="tierStyle(cell.tier)"
        >{{ cell.tier === 'direct' ? '직접' : '예측' }} · {{ cell.confidence }}</span>
        <span
          v-for="l in cell.labels"
          :key="l"
          class="text-xs text-(--sk-ink-muted)"
        >{{ l }}</span>
      </div>

      <div class="overflow-x-auto">
        <table class="border-collapse text-xs tabular-nums">
          <thead>
            <tr>
              <th class="p-1" />
              <th
                v-for="t in matrixOf(cell).tools"
                :key="t"
                class="p-1 text-(--sk-ink-muted) font-normal"
              >
                {{ shortLabel(t) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in matrixOf(cell).values"
              :key="i"
            >
              <th class="p-1 pr-2 text-right text-(--sk-ink-muted) font-normal">
                {{ shortLabel(matrixOf(cell).tools[i]!) }}
              </th>
              <td
                v-for="(v, j) in row"
                :key="j"
                class="p-1 text-center rounded"
                :style="cellStyle(v, i, j)"
                :title="pairTitle(cell, i, j, v)"
              >
                {{ i === j ? '—' : (v === null ? '·' : v.toFixed(3)) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { toolLabels } from '~/utils/toolLabels'
import type { SkewCondition, ToolRef } from '~/composables/useTttmApi'
import type { SkewMatrix } from '~/utils/tttmGrouping'

const props = defineProps<{ cells: SkewCondition[], tools: ToolRef[], tolerance: number }>()

const matrixOf = (cell: SkewCondition): SkewMatrix =>
  (cell.direct_skew_matrix ?? cell.predicted_skew_matrix)!

// The prefix is derived from the fleet's own labels, not the literal
// 'CD-SEM ' this used to strip — that quietly stopped shortening for any other
// tool family.
const labels = computed(() => toolLabels(props.tools))
const shortLabel = (eqp: string) => labels.value.shortLabel(eqp)

const tierStyle = (tier: string) =>
  tier === 'direct'
    ? { background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)' }
    : { background: 'var(--sk-muted-surface)', color: 'var(--sk-ink-muted)' }

const cellStyle = (v: number | null, i: number, j: number) => {
  if (i === j || v === null) return { color: 'var(--sk-ink-subtle)' }
  const tttm = v <= props.tolerance
  return tttm
    ? { background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)', fontWeight: 600 }
    : { background: 'var(--sk-bad-soft)', color: 'var(--sk-bad)' }
}

const pairTitle = (cell: SkewCondition, i: number, j: number, v: number | null) => {
  if (i === j || v === null) return ''
  const m = matrixOf(cell)
  const state = v <= props.tolerance ? 'TTTM' : 'tolerance 초과'
  return `${m.tools[i]} · ${m.tools[j]} = ${v.toFixed(3)} nm (${state})`
}
</script>
