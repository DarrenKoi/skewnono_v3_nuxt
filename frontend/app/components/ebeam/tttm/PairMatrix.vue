<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex flex-wrap items-center gap-2">
      <p class="sk-title">
        장비쌍 스큐 행렬
      </p>
      <span
        v-if="active"
        class="sk-count-chip"
      >불합격 {{ active.failingPairs }}쌍</span>
      <span
        v-if="active"
        class="ml-auto sk-meta"
      >
        <template v-if="active.cd.assumed">CD 미상 · 모니터 wafer {{ active.cd.nm }} nm 가정</template>
        <template v-else>CD {{ active.cd.nm.toFixed(1) }} nm</template>
        · 기준 {{ active.thresholdNm.toFixed(3) }} nm
        · {{ active.cell.tier === 'direct' ? '직접' : '예측' }}
        · {{ active.cell.confidence }}
        <template
          v-for="l in active.cell.labels"
          :key="l"
        > · {{ l }}</template>
      </span>
    </div>

    <!-- One cell at a time, worst first. The four matrices used to stack, which
         put the same 5x5 grid on screen four times and left the reader to work
         out which one decided anything; the tab label carries each cell's
         CD-relative index so the ordering is visible without opening them. -->
    <div
      v-if="cells.length"
      class="mt-3 flex flex-wrap gap-1.5"
    >
      <SkNavPill
        v-for="row in cells"
        :key="row.cell.cell_id"
        size="sm"
        :active="row.cell.cell_id === active?.cell.cell_id"
        @click="selectedId = row.cell.cell_id"
      >
        {{ cellLabel(row.cell) }}
        <template v-if="row.severity !== null">
          · {{ row.severity.toFixed(2) }}×
        </template>
      </SkNavPill>
    </div>

    <div
      v-if="active"
      class="mt-3 overflow-x-auto"
    >
      <table class="border-separate border-spacing-[3px] text-center font-mono text-[13px] tabular-nums">
        <thead>
          <tr>
            <th />
            <th
              v-for="t in active.matrix.tools"
              :key="t"
              class="px-2 py-1 sk-label font-semibold"
            >
              {{ shortLabel(t) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(cols, i) in active.matrix.values"
            :key="i"
          >
            <th class="pr-2 text-right sk-label font-semibold">
              {{ shortLabel(active.matrix.tools[i]!) }}
            </th>
            <td
              v-for="(v, j) in cols"
              :key="j"
              class="rounded-[var(--sk-r-sidebar)] px-2.5 py-1.5"
              :style="cellStyle(v, i, j)"
              :title="pairTitle(i, j, v)"
            >
              {{ i === j ? '—' : (v === null ? '·' : v.toFixed(3)) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p
      v-else
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      이 선택에는 장비쌍을 그릴 수 있는 셀이 없습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import { toolLabels } from '~/utils/toolLabels'
import { cellLabel, type RankedCell } from '~/utils/tttmCells'
import { ACTION_LIMIT_PERCENT, fractionOfLimit } from '~/utils/tttmLimits'
import type { ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  /** Already ranked worst-first — see rankCells in utils/tttmCells. */
  cells: RankedCell[]
  tools: ToolRef[]
}>()

// Sticky by cell_id, not by index: the tolerance never reorders the strip (see
// rankCells) but a recipe change replaces the cells outright, and an index would
// then silently point at a different cell than the one that was open.
const selectedId = ref<string | null>(null)
const active = computed(() =>
  props.cells.find(c => c.cell.cell_id === selectedId.value) ?? props.cells[0] ?? null
)

// The prefix is derived from the fleet's own labels, not a literal 'CD-SEM ',
// which quietly stopped shortening for any other tool family.
const labels = computed(() => toolLabels(props.tools))
const shortLabel = (eqp: string) => labels.value.shortLabel(eqp)

const cellStyle = (v: number | null, i: number, j: number) => {
  if (i === j || v === null) return { color: 'var(--sk-ink-subtle)' }
  return v <= (active.value?.thresholdNm ?? 0)
    ? { background: 'var(--sk-ok-soft)', color: 'var(--sk-ink)', fontWeight: 600 }
    : { background: 'var(--sk-bad-soft)', color: 'var(--sk-bad)', fontWeight: 700 }
}

const pairTitle = (i: number, j: number, v: number | null) => {
  const row = active.value
  if (!row || i === j || v === null) return ''
  const state = v <= row.thresholdNm ? 'TTTM' : 'tolerance 초과'
  // The fraction is what ranks pairs ACROSS cells: 0.24 nm at a 15 nm CD and
  // 0.24 nm at 68 nm are the same nanometres and nowhere near the same problem.
  // Named "CD 대비", never "한계 대비" — a pairwise limit is not fab policy, and
  // this file asserted one for a commit by calling it 한계.
  const index = fractionOfLimit(v, row.cd.nm)
  const basis = row.cd.assumed ? ' · CD 가정값' : ''
  return `${row.matrix.tools[i]} · ${row.matrix.tools[j]} = ${v.toFixed(3)} nm (${state})`
    + ` · CD 대비 ${index.toFixed(2)}× (CD의 ${ACTION_LIMIT_PERCENT}% 기준)${basis}`
}
</script>
