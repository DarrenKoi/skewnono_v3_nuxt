<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <p class="sk-title">
        consensus 잔차 · {{ windowLabel }}
      </p>
      <span class="sk-meta">PM/BM 한계 ±{{ actionLimit.toFixed(3) }} nm</span>
    </div>
    <div class="mt-3.5 space-y-1.5">
      <div
        v-for="d in sorted"
        :key="d.eqp_id"
        class="flex items-center gap-3 text-sm"
      >
        <span class="w-24 shrink-0 font-mono text-xs text-(--sk-ink)">{{ labelFor(d.eqp_id) }}</span>
        <div class="flex-1 relative h-3.5 rounded-[var(--sk-r-sidebar)] bg-(--sk-muted-surface)">
          <div
            class="absolute inset-y-0 left-1/2 w-px"
            :style="{ background: 'var(--sk-border)' }"
          />
          <!-- The measurement floor, drawn faintly: inside this band a tool is
               not distinguishable from consensus, so the bar means nothing. -->
          <div
            v-for="edge in floorEdges"
            :key="`floor-${edge}`"
            class="absolute inset-y-1 w-px"
            :style="{ left: `${edge}%`, background: 'var(--sk-border)' }"
          />
          <!-- The PM/BM action limit. This is the line that decides something. -->
          <div
            v-for="edge in actionEdges"
            :key="`action-${edge}`"
            class="absolute inset-y-0 w-px"
            :style="{ left: `${edge}%`, background: 'var(--sk-bad)', opacity: 0.45 }"
          />
          <div
            class="absolute inset-y-0.5 rounded"
            :style="barStyle(d.deviation)"
          />
        </div>
        <span
          class="w-16 shrink-0 text-right font-mono text-xs tabular-nums"
          :style="{ color: overLimit(d.deviation) ? 'var(--sk-bad)' : 'var(--sk-ink)' }"
        >{{ formatSignedNm(d.deviation) }}</span>
      </div>
    </div>
    <p class="mt-3 sk-field-label leading-relaxed">
      기간 내 일별 잔차의 중앙값을 선택한 장비 기준으로 다시 맞춘 값입니다. {{ verdict }}
      빨간 선은 PM/BM 한계({{ cdBasis }}), 옅은 선은 측정 불확도 ±{{ MEASUREMENT_FLOOR_NM.toFixed(2) }} nm입니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import { toolLabels } from '~/utils/toolLabels'
import {
  actionLimitNm,
  formatSignedNm,
  ACTION_LIMIT_PERCENT,
  MEASUREMENT_FLOOR_NM,
  type NominalCd
} from '~/utils/tttmLimits'
import type { DeviationRow } from '~/utils/tttmFleetSubset'
import type { ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  /**
   * Consensus residuals for the visible selection, already re-based.
   *
   * The one field of `FleetToday` this card reads. It used to take the whole
   * object and then resolve its own CD from `median_cd_nm`; now that the CD
   * arrives resolved, holding the rest would just be a wider dependency than
   * the card has — and would leave one prop carrying a `median_cd_nm` that
   * another prop already answers.
   */
  deviations: DeviationRow[]
  tools: ToolRef[]
  windowLabel: string
  /**
   * The CD this card's limit is drawn against, resolved by the parent.
   *
   * Passed rather than re-resolved here: `ExcludedTools` quotes the same
   * ±limit, and deriving it independently on both cards is how one of them
   * ends up quoting a different number than the other after a change to the
   * fallback. The parent resolves once; both cards read that one answer.
   */
  cd: NominalCd
}>()

// 1% of the CD actually measured, so this line moves with the recipe rather
// than sitting at a fixed 0.15 nm. `median_cd_nm` is nullable by contract; when
// it is null the parent falls back to the monitor wafer and `cd.assumed` says
// so in the caption, because a drawn-but-assumed limit that reads as measured
// is the failure this replaced.
const actionLimit = computed(() => actionLimitNm(props.cd.nm))

// Built as a string rather than as `<template v-if>` branches in the caption:
// those are block elements to the formatter, so it breaks them onto their own
// lines and the rendered sentence picks up a stray space before the closing
// paren.
const cdBasis = computed(() =>
  props.cd.assumed
    ? `CD 미상으로 모니터 웨이퍼 ${props.cd.nm} nm 가정`
    : `마지막 측정 CD ${props.cd.nm.toFixed(1)} nm의 ${ACTION_LIMIT_PERCENT}%`
)

// Rebuilt when the payload swaps the fleet; destructuring at setup would pin
// the first fab's labels for the life of the component.
const labels = computed(() => toolLabels(props.tools))
const labelFor = (eqp: string) => labels.value.labelFor(eqp)

// The action limit is always on the scale, so the red line cannot fall off the
// end of the track on a well-matched fleet and leave the bars looking unbounded.
const maxAbs = computed(() =>
  Math.max(
    actionLimit.value * 1.15,
    ...props.deviations.map(d => Math.abs(d.deviation))
  )
)
const sorted = computed(() =>
  [...props.deviations].sort((a, b) => a.deviation - b.deviation)
)

// Track positions (%) of a symmetric ±limit pair, measured from the centre line.
const edgesFor = (limit: number) => {
  const half = (limit / maxAbs.value) * 50
  return [50 - half, 50 + half]
}
const actionEdges = computed(() => edgesFor(actionLimit.value))
const floorEdges = computed(() => edgesFor(MEASUREMENT_FLOOR_NM))

const overLimit = (dev: number) => Math.abs(dev) > actionLimit.value

// The reading, said once so it does not have to be re-derived by eye from five
// bars. Counting rather than naming: which tools are out is already legible in
// the rows above, but "any at all?" is the question this card is asked first.
const verdict = computed(() => {
  const total = props.deviations.length
  const out = props.deviations.filter(d => overLimit(d.deviation)).length
  if (total === 0) return '표시할 장비가 없습니다.'
  return out === 0
    ? `${total}대 모두 PM/BM 한계 안입니다.`
    : `${total}대 중 ${out}대가 PM/BM 한계 밖입니다.`
})

// Bar grows from the center line toward the sign direction.
const barStyle = (dev: number) => {
  const half = (Math.abs(dev) / maxAbs.value) * 50
  const bg = overLimit(dev) ? 'var(--sk-bad)' : 'var(--sk-ok)'
  return dev >= 0
    ? { left: '50%', width: `${half}%`, background: bg }
    : { right: '50%', width: `${half}%`, background: bg }
}
</script>
