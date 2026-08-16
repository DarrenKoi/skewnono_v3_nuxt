<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <p class="sk-title">
        장비 그룹 배치도
      </p>
      <p
        class="font-mono text-xs tabular-nums"
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
      class="mt-2 mx-auto aspect-square w-full max-w-md"
    />
    <p
      v-else
      class="mt-3 sk-body text-(--sk-ink-muted)"
    >
      배치할 수 있는 장비가 2대 미만이라 지도를 그리지 않습니다.
    </p>

    <div
      v-if="map.detached.length"
      class="mt-3 flex flex-wrap items-center gap-2"
    >
      <span class="sk-field-label">지도에서 제외:</span>
      <span
        v-for="eqp in map.detached"
        :key="eqp"
        class="sk-badge bg-(--sk-chip-bg) text-(--sk-chip-text)"
      >{{ labelFor(eqp) }}</span>
      <span class="sk-field-label">
        — 다른 장비와 겹치는 측정이 없어 거리를 정의할 수 없습니다.
      </span>
    </div>

    <p class="mt-1.5 sk-field-label leading-relaxed">
      점 사이 거리만 의미가 있습니다. 점 크기 = 평균 skew(Score).
      <EbeamTttmCaptionMore>
        축에는 단위가 없고 회전·반전해도 같은 지도입니다. 빨강은 <strong>오늘 장비
          그룹 행렬 기준</strong>으로 가장 가까운 장비마저 허용오차
        {{ thresholdBasis }} 밖인 장비이며, N배화 판정은 점유 셀 전체를 교차한
        결과라 이 지도와 다를 수 있습니다 — 그쪽은 위 추천 카드를 보십시오.
        초록 테두리는 그 <strong>N배화 그룹</strong>이라 위치가 아니라 판정으로
        그려집니다. 그래서 테두리 안에 있는데 빨간 점이거나, 가까이 있는데 테두리
        밖인 장비가 나올 수 있고, 그것이 두 계산이 갈라진 지점입니다.
      </EbeamTttmCaptionMore>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption, SeriesOption } from 'echarts'
import { fleetMap } from '~/utils/fleetMap'
import { mean } from '~/utils/stats'
import { SK_STATE } from '~/utils/chartPalette'
import { CHART_AXIS_LABEL } from '~/utils/chartType'
import type { PairReading } from '~/utils/tttmCells'
import { toolLabels } from '~/utils/toolLabels'
import { effectiveToleranceNm, resolveNominalCd } from '~/utils/tttmLimits'
import type { FleetToday, ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  fleet: FleetToday
  tools: ToolRef[]
  /** CD-relative; converted against THIS matrix's own CD below, not against nm. */
  toleranceIndex: number
  /**
   * The 1차 추천 group's members, drawn as a boundary over the scatter.
   *
   * The card is titled 장비 그룹 배치도 and until now drew no 그룹 — only
   * coloured points — so the reader had to hold the recommendation card in
   * their head and match ids by eye.
   *
   * Note this deliberately mixes two computations, exactly as the design does:
   * the POSITIONS come from `fleet_today.matrix` (one matrix) while MEMBERSHIP
   * comes from the AND-fold across every occupied cell. They can disagree, and
   * a member can sit visually apart from its group. The caption already says
   * so, and the boundary is drawn from membership rather than from the
   * geometry, so it never invents a group the fold did not find.
   */
  groupTools?: string[]
  /**
   * The blocking pair to annotate — which two tools produced the worst blocked
   * skew, and how large it was. Drawn as the dashed connector in the design.
   *
   * The reading itself, not a restatement of its fields: the same object the
   * exclusion card explains in words, so the two cannot describe different
   * pairs.
   */
  blockedPair?: PairReading | null
  /**
   * One tool to visually anchor — pm-tune's picked tool, the one in (or fresh
   * out of) its PM window. Drawn as an ink ring around its point plus a bold
   * label, never a recolor: red already means "no partner inside tolerance",
   * and overloading it would make the pick look like a finding.
   */
  pickedTool?: string | null
  /**
   * Overrides the halo's `N배화 그룹 · {n}대` caption — pm-tune writes the
   * prospective form (`… → {n+1}대 (튜닝 시)`). The ring itself still encloses
   * only the CURRENT members; only the words change.
   */
  haloLabel?: string
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

const pointAt = computed(() => new Map(map.value.points.map(p => [p.eqp_id, p])))

/**
 * The circle enclosing the group's mappable members, in DATA space.
 *
 * A circle rather than a hull because both axes already share one domain and
 * the box is `aspect-square` (see the template), so one data unit is the same
 * number of pixels horizontally and vertically — which is the whole reason the
 * map is readable as distance. Under that construction a data-space circle
 * lands as a pixel circle, and no per-axis correction is needed.
 *
 * Members the map dropped (`map.detached` — a tool sharing no measurement with
 * anyone has no defined distance, so MDS cannot place it) are simply not
 * enclosed. Under two enclosable members there is no region to draw.
 */
const groupHalo = computed(() => {
  const members = (props.groupTools ?? [])
    .map(eqp => pointAt.value.get(eqp))
    .filter(p => p !== undefined)
  if (members.length < 2) return null

  const cx = mean(members.map(p => p.x))
  const cy = mean(members.map(p => p.y))
  const reach = Math.max(...members.map(p => Math.hypot(p.x - cx, p.y - cy)))
  // Padding is proportional so the ring clears the symbols at any zoom, with a
  // floor for the degenerate case of members sitting on top of each other.
  const span = domain.value.max - domain.value.min
  return { cx, cy, r: reach * 1.25 + span * 0.06, n: members.length }
})

/** The blocked pair as map coordinates, when both ends were placed. */
const blockedLink = computed(() => {
  const pair = props.blockedPair
  if (!pair) return null
  const a = pointAt.value.get(pair.a)
  const b = pointAt.value.get(pair.b)
  if (!a || !b) return null
  return { a, b, skewNm: pair.skewNm }
})

/**
 * What sits UNDER the scatter: the group boundary and the blocked-pair link.
 *
 * Both are `silent`, so they never intercept a hover meant for a point, and
 * both are omitted entirely when their inputs are absent — an empty group or an
 * unplaceable endpoint draws nothing rather than a degenerate ring at the
 * origin.
 */
const backdrop = computed<SeriesOption[]>(() => {
  const out: SeriesOption[] = []
  const halo = groupHalo.value

  if (halo) {
    out.push({
      type: 'custom',
      silent: true,
      z: 1,
      // One datum, one renderItem call. The shape is computed in PIXELS on
      // every render rather than baked once, which is what keeps it aligned
      // through the host ResizeObserver's re-layout.
      data: [[halo.cx, halo.cy]],
      renderItem: (_params: unknown, api: unknown) => {
        const { coord } = api as { coord: (d: number[]) => number[] }
        const centre = coord([halo.cx, halo.cy])
        const edge = coord([halo.cx + halo.r, halo.cy])
        const cx = centre[0] ?? 0
        const cy = centre[1] ?? 0
        const r = Math.abs((edge[0] ?? 0) - cx)
        return {
          type: 'group',
          children: [
            {
              type: 'circle',
              shape: { cx, cy, r },
              // Alpha over the canvas rather than a fixed soft token, so the
              // ring reads the same weight on the warm paper and in dark mode.
              style: {
                fill: SK_STATE.ok,
                opacity: 0.12,
                stroke: SK_STATE.ok,
                lineWidth: 1,
                lineDash: [4, 4]
              }
            },
            {
              type: 'text',
              style: {
                text: props.haloLabel ?? `N배화 그룹 · ${halo.n}대`,
                x: cx,
                y: cy - r - 6,
                textAlign: 'center',
                textVerticalAlign: 'bottom',
                fill: SK_STATE.ok,
                ...CHART_AXIS_LABEL
              }
            }
          ]
        }
      }
    })
  }

  const link = blockedLink.value
  if (link) {
    out.push({
      type: 'lines',
      coordinateSystem: 'cartesian2d',
      silent: true,
      z: 2,
      data: [{ coords: [[link.a.x, link.a.y], [link.b.x, link.b.y]] }],
      lineStyle: { color: SK_STATE.bad, width: 1.5, type: [5, 4], opacity: 0.9 },
      label: {
        show: true,
        position: 'middle',
        formatter: `${link.skewNm.toFixed(3)} nm`,
        color: SK_STATE.bad,
        ...CHART_AXIS_LABEL
      }
    })
  }

  return out
})

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
    series: [...backdrop.value, {
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
        itemStyle: {
          color: p.nearest > thresholdNm.value ? SK_STATE.bad : sk.value.series,
          // The picked tool gets an ink RING, orthogonal to the red/series
          // color: the fill keeps saying what the tolerance says, the ring
          // says which point the page is currently arguing about.
          ...(p.eqp_id === props.pickedTool
            ? { borderColor: sk.value.ink, borderWidth: 2 }
            : {})
        },
        ...(p.eqp_id === props.pickedTool
          ? { label: { fontWeight: 700 as const } }
          : {})
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
        // From `chartType`, not hand-written. DESIGN.md §The row-card tier:
        // ECharts paints to a canvas where the sk-* classes cannot reach, so
        // `utils/chartType.ts` restates the floor for that one context and
        // "every chart on these screens reads from it". These labels are
        // eqp_ids — data values — and were sitting at 11px, under the floor.
        ...CHART_AXIS_LABEL
      },
      // A tightly-matched group is a tight CLUSTER by construction, so its
      // labels collide exactly where the map is most worth reading. Shift them
      // apart first, and drop whatever still will not fit.
      //
      // `shiftY` alone was the previous rule, on the argument that a dropped
      // label reads as a tool that is not in the fleet. That holds at five
      // tools. At the seventeen R3 actually has, shifting cannot find the room
      // and the cluster renders as a stack of overlapping ids — which does not
      // name a single tool either, and additionally makes the chart look
      // broken. Hiding is the better failure: the ring already says how many
      // tools are in the group, the red points and the connector carry the
      // finding, and hovering any point names it.
      labelLayout: { moveOverlap: 'shiftY', hideOverlap: true }
    }]
  }
})

useEchart(el, chartOption, { exportName: 'tttm-fleet-map' })
</script>
