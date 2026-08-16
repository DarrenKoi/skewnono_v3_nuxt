<template>
  <div class="dashboard-surface rounded-2xl p-5 space-y-5">
    <div class="space-y-1">
      <p class="text-xs text-(--sk-ink-subtle)">
        장비쌍 스큐 행렬 (TTTM 근거 · 셀별)
      </p>
      <p class="text-[11px] text-(--sk-ink-subtle)">
        셀은 <strong>CD 대비 지수</strong>가 큰 순서로 정렬했습니다. 지수는
        해당 셀 최악 장비쌍의 스큐를 그 셀 CD의 {{ percent }}%로 나눈 값이라,
        패턴 크기가 다른 셀끼리도 비교할 수 있습니다 — nm 값만으로는 비교가
        되지 않습니다. 합격/불합격 선은 위의 tolerance 이며,
        <strong>이 지수는 순위를 매길 뿐 판정하지 않습니다</strong>
        (CD의 {{ percent }}% 규칙은 장비 1대를 consensus 와 비교하는 공장
        기준이고, 장비쌍에 적용하는 것은 아직 확인되지 않은 확장입니다).
      </p>
    </div>

    <div
      v-for="row in rankedCells"
      :key="row.cell.cell_id"
      class="space-y-2"
    >
      <div class="flex items-center gap-2 text-sm">
        <span class="font-medium text-(--sk-ink)">
          {{ row.cell.beam_condition }} · {{ row.cell.axis }} · {{ row.cell.cd_band }}nm
        </span>
        <span
          class="px-1.5 py-0.5 rounded text-xs"
          :style="tierStyle(row.cell.tier)"
        >{{ row.cell.tier === 'direct' ? '직접' : '예측' }} · {{ row.cell.confidence }}</span>
        <!-- The measured CD and this cell's rank index. NOT labelled 한계
             (limit): the CD ratio is the fab's rule for one tool against
             consensus, so calling the pairwise number a limit would assert
             something the fab never said. It is stated as an index, in the
             units it actually has — a multiple of CD's 1%. -->
        <span class="text-xs text-(--sk-ink-muted)">
          <template v-if="row.cd.assumed">CD 미상 · 모니터 wafer {{ row.cd.nm }} nm 가정</template>
          <template v-else>CD {{ row.cd.nm.toFixed(1) }} nm</template>
        </span>
        <span
          v-if="row.severity !== null"
          class="px-1.5 py-0.5 rounded text-xs tabular-nums"
          :style="{ background: 'var(--sk-muted-surface)', color: 'var(--sk-ink-muted)' }"
          :title="`이 셀 최악 장비쌍 ÷ (CD의 ${percent}%)`"
        >CD 대비 {{ row.severity.toFixed(2) }}×</span>
        <!-- What the knob costs THIS cell. Two cells at different CDs pass
             different nm at the same slider position, so the number the
             colouring uses has to be visible per cell. -->
        <span class="text-xs text-(--sk-ink-subtle)">
          기준 {{ row.threshold.toFixed(3) }} nm
        </span>
        <span
          v-for="l in row.cell.labels"
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
                v-for="t in row.matrix.tools"
                :key="t"
                class="p-1 text-(--sk-ink-muted) font-normal"
              >
                {{ shortLabel(t) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(cols, i) in row.matrix.values"
              :key="i"
            >
              <th class="p-1 pr-2 text-right text-(--sk-ink-muted) font-normal">
                {{ shortLabel(row.matrix.tools[i]!) }}
              </th>
              <td
                v-for="(v, j) in cols"
                :key="j"
                class="p-1 text-center rounded"
                :style="cellStyle(row, v, i, j)"
                :title="pairTitle(row, i, j, v)"
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
import {
  fractionOfLimit,
  worstFractionOfLimit,
  resolveNominalCd,
  PM_BM_ACTION_LIMIT_RATIO,
  type NominalCd
} from '~/utils/tttmLimits'
import { effectiveToleranceNm, type SkewMatrix } from '~/utils/tttmGrouping'
import type { SkewCondition, ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  cells: SkewCondition[]
  tools: ToolRef[]
  /** CD-relative, not nm — each cell converts it against its own CD below. */
  toleranceIndex: number
}>()

/**
 * A cell with everything derived from its CD resolved once.
 *
 * The CD fallback used to be re-walked per cell by the threshold, the severity
 * and every tooltip; deriving it here means one resolution per cell per render
 * and, more usefully, makes it impossible for two of those to disagree.
 */
interface RankedCell {
  cell: SkewCondition
  matrix: SkewMatrix
  cd: NominalCd
  /** Worst pair as a CD-relative index; null when nothing was measured. */
  severity: number | null
  /** The knob converted into this cell's own nanometres. */
  threshold: number
}

const percent = computed(() => (PM_BM_ACTION_LIMIT_RATIO * 100).toFixed(0))

// THE ranking. Cells are shown worst-first by the CD-normalised index, not by
// raw nm and not in payload order — which is the whole point of carrying a CD:
// a 0.13 nm pair at a 68 nm CD outranks nothing, while the same 0.13 nm on the
// monitor wafer is most of the way to the fab's limit. Sorting by nm would put
// them in the wrong order and payload order ignores severity entirely.
//
// Cells with no measured pair sort last: they carry no evidence, so they
// cannot be "better" than a cell that does.
const rankedCells = computed<RankedCell[]>(() =>
  props.cells
    .map((cell): RankedCell => {
      const matrix = (cell.direct_skew_matrix ?? cell.predicted_skew_matrix)!
      const cd = resolveNominalCd(cell.median_cd_nm)
      return {
        cell,
        matrix,
        cd,
        severity: worstFractionOfLimit(matrix.values, cd.nm),
        threshold: effectiveToleranceNm(props.toleranceIndex, cd.nm)
      }
    })
    .sort((a, b) => (b.severity ?? -1) - (a.severity ?? -1))
)

// The prefix is derived from the fleet's own labels, not the literal
// 'CD-SEM ' this used to strip — that quietly stopped shortening for any other
// tool family.
const labels = computed(() => toolLabels(props.tools))
const shortLabel = (eqp: string) => labels.value.shortLabel(eqp)

const tierStyle = (tier: string) =>
  tier === 'direct'
    ? { background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)' }
    : { background: 'var(--sk-muted-surface)', color: 'var(--sk-ink-muted)' }

const cellStyle = (row: RankedCell, v: number | null, i: number, j: number) => {
  if (i === j || v === null) return { color: 'var(--sk-ink-subtle)' }
  return v <= row.threshold
    ? { background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)', fontWeight: 600 }
    : { background: 'var(--sk-bad-soft)', color: 'var(--sk-bad)' }
}

const pairTitle = (row: RankedCell, i: number, j: number, v: number | null) => {
  if (i === j || v === null) return ''
  const state = v <= row.threshold ? 'TTTM' : 'tolerance 초과'
  // The fraction is what ranks pairs ACROSS cells: 0.24 nm at a 15 nm CD and
  // 0.24 nm at 68 nm are the same nanometres and nowhere near the same problem.
  // Named "CD 대비", never "한계 대비" — see the header comment.
  const index = fractionOfLimit(v, row.cd.nm)
  const basis = row.cd.assumed ? ' · CD 가정값' : ''
  return `${row.matrix.tools[i]} · ${row.matrix.tools[j]} = ${v.toFixed(3)} nm (${state})`
    + ` · CD 대비 ${index.toFixed(2)}×${basis}`
}
</script>
