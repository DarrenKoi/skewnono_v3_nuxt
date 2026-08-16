<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <p class="text-xs text-(--sk-ink-subtle)">
        장비 그룹 배치도 · 서로의 skew 거리를 2D로 펼친 지도
      </p>
      <p
        class="text-[11px] tabular-nums"
        :style="{ color: stress.color }"
      >
        stress {{ map.stress.toFixed(3) }} · {{ stress.text }}
      </p>
    </div>

    <!-- Square by construction. Both axes share one domain (see `domain`), so
         the box has to be square too — on a wide box the same nm would be
         drawn longer horizontally than vertically and every distance on a map
         whose whole point is distance would be misread. -->
    <div
      v-if="map.points.length"
      ref="el"
      class="mt-3 mx-auto aspect-square w-full max-w-sm"
    />
    <p
      v-else
      class="mt-3 text-sm text-(--sk-ink-muted)"
    >
      배치할 수 있는 장비가 2대 미만이라 지도를 그리지 않습니다.
    </p>

    <div
      v-if="map.detached.length"
      class="mt-3 flex flex-wrap items-center gap-2"
    >
      <span class="text-[11px] text-(--sk-ink-subtle)">지도에서 제외:</span>
      <span
        v-for="eqp in map.detached"
        :key="eqp"
        class="rounded-(--sk-r-chip) px-1.5 py-0.5 text-[11px] bg-(--sk-chip-bg) text-(--sk-chip-text)"
      >{{ labelFor(eqp) }}</span>
      <span class="text-[11px] text-(--sk-ink-subtle)">
        — 다른 장비와 겹치는 측정이 없어 거리를 정의할 수 없습니다.
      </span>
    </div>

    <p class="mt-2 text-[11px] text-(--sk-ink-subtle)">
      축에는 단위가 없습니다. <strong>점 사이의 거리만</strong> 의미가 있으며, 회전·반전해도
      같은 지도입니다. 점 크기는 나머지 장비까지의 평균 skew(Score)이고, 빨강은
      <strong>오늘 장비 그룹 행렬 기준</strong>으로 가장 가까운 장비마저 허용오차
      {{ thresholdBasis }} 밖인 장비입니다. N배화 그룹 판정은 점유 셀
      전체를 교차한 결과라 이 지도와 다를 수 있으므로, 그쪽은 위 추천 카드를
      보십시오.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { fleetMap } from '~/utils/fleetMap'
import { SK_STATE } from '~/utils/chartPalette'
import { toolLabels } from '~/utils/toolLabels'
import { effectiveToleranceNm, resolveNominalCd } from '~/utils/tttmLimits'
import type { FleetToday, ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  fleet: FleetToday
  tools: ToolRef[]
  /** CD-relative; converted against THIS matrix's own CD below, not against nm. */
  toleranceIndex: number
}>()

// fleet_today carries its own CD, so the map's red rule scales the same way the
// cells do. Using the raw nm knob here would judge the fleet matrix at the
// monitor wafer's standard no matter what was actually measured.
const cd = computed(() => resolveNominalCd(props.fleet.median_cd_nm))
const thresholdNm = computed(() => effectiveToleranceNm(props.toleranceIndex, cd.value.nm))

// A string rather than `<template v-if>` branches in the caption — see the
// note on FleetStatus's `cdBasis` for why.
const thresholdBasis = computed(() => {
  const basis = cd.value.assumed ? ' 가정' : ''
  return `${thresholdNm.value.toFixed(3)} nm`
    + ` (CD 대비 ${props.toleranceIndex.toFixed(2)}× · 이 행렬의 CD ${cd.value.nm.toFixed(1)} nm${basis})`
})

const el = ref<HTMLDivElement | null>(null)
const sk = useChartPalette()

const map = computed(() => fleetMap(props.fleet.matrix))

const labels = computed(() => toolLabels(props.tools))
const labelFor = (eqp: string) => labels.value.labelFor(eqp)

// Stress-1 reading, on the conventional Kruskal bands. Said out loud because a
// 2D map of non-Euclidean distances can be badly wrong while still looking
// tidy, and the reader has no other cue that it is. Text and tone come from one
// ladder so the wording and the color can never disagree about which band it is.
const stress = computed(() => {
  const s = map.value.stress
  if (s < 0.05) return { text: '거리 재현 우수', color: 'var(--sk-ink-subtle)' }
  if (s < 0.10) return { text: '양호', color: 'var(--sk-ink-subtle)' }
  if (s < 0.20) return { text: '보통 — 위치는 참고만', color: 'var(--sk-ink-muted)' }
  return { text: '나쁨 — 아래 쌍별 행렬을 보십시오', color: 'var(--sk-bad)' }
})

// One square domain shared by both axes. MDS distances are only readable if the
// two axes are on the SAME scale — letting ECharts fit each axis independently
// would stretch one direction and silently misstate every gap on the chart.
const domain = computed(() => {
  // Pool both coordinates: the output is a single square window containing
  // every point, so there is nothing to gain by tracking the axes separately.
  const all = map.value.points.flatMap(p => [p.x, p.y])
  if (!all.length) return { min: -1, max: 1 }
  const lo = Math.min(...all)
  const hi = Math.max(...all)
  const centre = (lo + hi) / 2
  const pad = ((hi - lo) / 2 || 0.1) * 1.35
  return { min: centre - pad, max: centre + pad }
})

// The datum tuple, named once. Spelling it inline at each formatter is how the
// meaning of `value[3]` gets lost.
type FleetValue = [x: number, y: number, score: number, nearest: number]
interface FleetDatum { name: string, value: FleetValue }

const chartOption = computed<EChartsOption>(() => {
  const points = map.value.points
  const maxScore = Math.max(...points.map(p => p.score), 1e-9)
  // A factory, not one shared object: both axes must stay identical for the
  // square domain to mean anything, but handing ECharts the same reference
  // twice is asking for trouble in its option merge.
  const axis = () => ({
    type: 'value' as const,
    min: domain.value.min,
    max: domain.value.max,
    axisLabel: { show: false },
    splitLine: { lineStyle: { color: sk.value.muted, opacity: 0.25 } }
  })

  return {
    // Equal insets on all four sides, so the square box yields a square plot
    // area and the shared axis domain really is drawn at one scale.
    grid: { top: 20, right: 20, bottom: 20, left: 20 },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const { name, value } = (p as { data: FleetDatum }).data
        return `${labelFor(name)}<br/>최근접 ${value[3].toFixed(3)} nm`
          + `<br/>Score(평균) ${value[2].toFixed(3)} nm`
      }
    },
    xAxis: axis(),
    yAxis: axis(),
    series: [{
      type: 'scatter',
      data: points.map(p => ({
        name: p.eqp_id,
        value: [p.x, p.y, p.score, p.nearest],
        // Red = no partner inside the tolerance IN THIS MATRIX. Compared
        // against `nearest`, not `score`, because the tolerance is a pairwise
        // spec — see FleetPoint.nearest.
        //
        // Deliberately NOT the same statement as "belongs to no N배화 group":
        // that comes from tttmGrouping's AND-fold across every occupied cell,
        // while fleet_today.matrix is one matrix. They coincide in the mock
        // only because it reuses cell bc1-X-25-50-e7's values, and the office
        // adapter owes us no such thing. The caption says which one this is.
        itemStyle: { color: p.nearest > thresholdNm.value ? SK_STATE.bad : sk.value.series }
      })),
      // Area, not radius, tracks the score — a radius-encoded circle overstates
      // a large value by its square.
      symbolSize: (v: unknown) => {
        const score = (v as FleetValue)[2]
        return 12 + Math.sqrt(score / maxScore) * 22
      },
      label: {
        show: true,
        position: 'bottom',
        distance: 6,
        formatter: (p: unknown) => labelFor((p as { data: FleetDatum }).data.name),
        color: sk.value.ink,
        fontSize: 11
      },
      // A tightly-matched group is a tight CLUSTER by construction, so its
      // labels collide exactly where the map is most worth reading. Shift them
      // apart rather than hiding any — a dropped label reads as a tool that is
      // not in the fleet at all. No visible effect on the 5-tool mock, where
      // the points are already far enough apart; it is the 10-12 tool fleets
      // the office actually runs that need it.
      labelLayout: { moveOverlap: 'shiftY' }
    }]
  }
})

useEchart(el, chartOption, { exportName: 'tttm-fleet-map' })
</script>
