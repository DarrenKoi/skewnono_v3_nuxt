<template>
  <div class="dashboard-surface min-w-0 rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <div class="flex flex-wrap items-baseline gap-2">
        <p class="sk-title">
          장비 그룹 배치도
        </p>
        <!-- The group's size, in the header rather than over the plot. It used
             to caption a circle drawn around the members; the circle is gone
             (see `groupCentroid`) and this is the half of it that was true.
             Same token as the 1차 그룹 badge on the 튜닝할 장비 card, because it
             is the same assertion. -->
        <span
          v-if="groupCaption"
          class="sk-badge bg-(--sk-ok-soft) text-(--sk-ink)"
        >{{ groupCaption }}</span>
      </div>
      <!-- PCA: how much of the spread the two drawn axes carry — the honesty
           figure for a projection, the way stress is for MDS. -->
      <p
        v-if="pca"
        class="font-mono text-xs tabular-nums"
        :style="{ color: explainedTone.color }"
      >
        PCA · PC1 {{ pct(pca.explained[0]) }} · PC2 {{ pct(pca.explained[1]) }} · parameter {{ pca.parameters.length }}개{{ explainedTone.text }}
      </p>
      <p
        v-else
        class="font-mono text-xs tabular-nums"
        :style="{ color: stress.color }"
      >
        stress {{ map.stress.toFixed(3) }} · {{ stress.text }}
      </p>
    </div>

    <div
      v-if="$slots.default"
      class="mt-3 max-w-md"
    >
      <slot />
    </div>
    <select
      class="sr-only focus:not-sr-only"
      aria-label="배치도에서 튜닝할 장비 선택"
      :value="pickedTool ?? ''"
      @change="emit('update:pickedTool', ($event.target as HTMLSelectElement).value || null)"
    >
      <option value="">
        선택 해제
      </option>
      <option
        v-for="point in map.points"
        :key="point.eqp_id"
        :value="point.eqp_id"
      >
        {{ labelFor(point.eqp_id) }}
      </option>
    </select>

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

    <!-- Legend, ALWAYS visible — not folded into 자세히.
         This card carries two different verdicts at once: the FILL is a
         pairwise tolerance reading, the OUTLINE is group membership. Nothing
         about a blue dot says "in the group", and a reader who assumes it does
         gets the recommendation backwards. That inference was available for as
         long as the colours went unexplained above the fold, so the swatches
         sit here rather than one click away.
         The swatch colours are bound to the SAME values the series use, so the
         legend cannot drift from what the canvas actually paints. -->
    <div
      v-if="map.points.length"
      class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--sk-ink-muted)"
    >
      <span class="inline-flex items-center gap-1">
        <span
          class="h-3 w-3 shrink-0 rounded-full"
          :style="{ backgroundColor: sk.series }"
        />
        허용 오차 안에 맞는 장비 있음
      </span>
      <span class="inline-flex items-center gap-1">
        <span
          class="h-3 w-3 shrink-0 rounded-full"
          :style="{ backgroundColor: SK_STATE.bad }"
        />
        허용 오차 안에 맞는 장비 없음
      </span>
      <span
        v-if="groupCentroid"
        class="inline-flex items-center gap-1"
      >
        <span
          class="h-3 w-3 shrink-0 rounded-full border-2 bg-transparent"
          :style="{ borderColor: SK_STATE.ok }"
        />
        1차 N배화 그룹 소속
      </span>
      <span class="text-(--sk-ink-subtle)">초록 테두리는 그룹 소속, 진한 테두리는 선택한 장비입니다.</span>
    </div>

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
        <template v-if="pca">선택한 측정 항목이 누락되어 배치할 수 없습니다.</template>
        <template v-else>공통 측정이 없어 거리를 계산할 수 없습니다.</template>
      </span>
    </div>

    <p class="mt-1.5 sk-field-label leading-relaxed">
      <template v-if="pca">
        선택한 측정 항목의 잔차로 배치하며, 초록 십자가 튜닝 목표인 그룹 중심입니다.
      </template>
      <template v-else>
        장비별 마지막 측정의 쌍별 거리로 배치하며, 측정 항목이 없어 튜닝 목표는 계산하지 않습니다.
      </template>
      점을 누르면 튜닝 목표가 표시되며, 다시 누르거나 빈 곳을 누르면 선택이 해제됩니다.
      휠로 확대하고 끌어서 이동합니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption, SeriesOption } from 'echarts'
import { nearestPoint } from '~/utils/chartNearest'
import { fleetMap } from '~/utils/fleetMap'
import type { PcaResult } from '~/utils/parameterPca'
import { mean } from '~/utils/stats'
import { SK_STATE } from '~/utils/chartPalette'
import { CHART_AXIS_LABEL } from '~/utils/chartType'
import type { PairReading } from '~/utils/tttmCells'
import { toolLabels } from '~/utils/toolLabels'
import { effectiveToleranceNm, resolveNominalCd } from '~/utils/tttmLimits'
import type { FleetToday, ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  fleet: Pick<FleetToday, 'matrix' | 'median_cd_nm'>
  tools: ToolRef[]
  /** CD-relative; converted against THIS matrix's own CD below, not against nm. */
  toleranceIndex: number
  /**
   * The 1차 추천 group's members, outlined green on the scatter.
   *
   * The card is titled 장비 그룹 배치도 and for a while drew no readable 그룹 —
   * first only coloured points, then an enclosing circle that also swallowed
   * non-members — so the reader had to hold the recommendation card in their
   * head and match ids by eye.
   *
   * Note this deliberately mixes two computations, exactly as the design does:
   * the POSITIONS come from `fleet_today.matrix` (one matrix) while MEMBERSHIP
   * comes from the AND-fold across every occupied cell. They can disagree, and
   * a member can sit visually apart from its group. Marking it PER POINT is
   * what keeps that disagreement legible: an outline states a fact about one
   * tool, where a region silently states one about whatever falls inside it.
   */
  groupTools?: string[]
  /**
   * The blocking pair to annotate — which two tools produced the worst blocked
   * skew, and how large it was. Drawn as a solid connector.
   *
   * The reading itself, not a restatement of its fields: the same object the
   * exclusion card explains in words, so the two cannot describe different
   * pairs.
   */
  blockedPair?: PairReading | null
  /**
   * The tool selected by a map click. Drawn as an ink ring around its point plus a bold
   * label, never a recolor: red already means "no partner inside tolerance",
   * and overloading it would make the pick look like a finding.
   */
  pickedTool?: string | null
  /**
   * PCA placement over the picked parameters (utils/parameterPca). When
   * given, positions, `score` and `nearest` are in CD-relative index units
   * and the red rule compares `nearest` to `toleranceIndex` directly; when
   * null the map falls back to classical MDS over `fleet.matrix` in nm.
   */
  pca?: PcaResult | null
}>()

// fleet_today carries its own CD, so the map's red rule scales the same way the
// cells do. Using the raw nm knob here would judge the fleet matrix at the
// monitor wafer's standard no matter what was actually measured.
const cd = computed(() => resolveNominalCd(props.fleet.median_cd_nm))
const thresholdNm = computed(() => effectiveToleranceNm(props.toleranceIndex, cd.value.nm))

const emit = defineEmits<{ 'update:pickedTool': [value: string | null] }>()

const el = ref<HTMLDivElement | null>(null)
const sk = useChartPalette()
// The card's own background, for the outline pass under the centroid marker —
// a stroke drawn straight onto a symbol is unreadable in either theme.
const { surface } = useEchartsTheme()

// Same point shape from either engine, so everything below (halo, link,
// domain, labels) is written once. Only the units differ — `unit` says which.
const map = computed(() =>
  props.pca
    ? { points: props.pca.points, detached: props.pca.detached, stress: 0 }
    : fleetMap(props.fleet.matrix)
)
const threshold = computed(() => (props.pca ? props.toleranceIndex : thresholdNm.value))
const unit = (v: number) => (props.pca ? `CD 대비 ${v.toFixed(2)}×` : `${v.toFixed(3)} nm`)

const pct = (fraction: number) => `${(fraction * 100).toFixed(0)}%`
// Two components carrying under half the spread is a picture to read with the
// pairwise matrix beside it — the same warning the stress ladder gives MDS.
const explainedTone = computed(() => {
  const carried = (props.pca?.explained[0] ?? 0) + (props.pca?.explained[1] ?? 0)
  if (carried >= 0.8) return { text: '', color: 'var(--sk-ink-subtle)' }
  if (carried >= 0.5) return { text: ' · 위치는 참고만', color: 'var(--sk-ink-muted)' }
  return { text: ' · 2축으로 부족 — 셀 행렬을 보십시오', color: 'var(--sk-bad)' }
})
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

/** Fast membership lookup for the per-point outline below. */
const groupSet = computed(() => new Set(props.groupTools ?? []))

/**
 * The group's centre of gravity, in DATA space — and NOT a region.
 *
 * This used to also return a radius, and the map drew a circle of it around the
 * members. That circle was a lie by construction: its radius was the farthest
 * member's, so any NON-member closer to the centroid than that member fell
 * inside it and read as enclosed. On R3 / QC_DAILY_MATCH with three parameters
 * two of the three excluded tools (ECXDX382, HCDX131) sat inside the "13대"
 * ring, painted the same blue as the members, and nothing on the card said
 * otherwise.
 *
 * The error underneath it was a category one, not an arithmetic one. Positions
 * come from PCA over the parameter profile while MEMBERSHIP comes from the
 * AND-fold across every occupied cell — the two are allowed to disagree (the
 * caption says so), so membership is not a region in this space and no shape
 * drawn from the geometry can state it. It is a per-tool fact, so it is now
 * drawn per tool: the green outline in `chartOption`.
 *
 * Members the map dropped (`map.detached` — a tool sharing no measurement with
 * anyone has no defined distance, so MDS cannot place it) do not move the
 * centroid. Even one placed member defines the same centre that tuningTarget uses.
 */
const groupCentroid = computed(() => {
  const members = (props.groupTools ?? [])
    .map(eqp => pointAt.value.get(eqp))
    .filter(p => p !== undefined)
  if (members.length === 0) return null

  return {
    cx: mean(members.map(p => p.x)),
    cy: mean(members.map(p => p.y)),
    n: members.length
  }
})

const groupCaption = computed(() =>
  groupCentroid.value ? `N배화 그룹 · ${groupCentroid.value.n}대` : null
)

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
 * What sits around the scatter: the group's centroid and the blocked-pair link.
 *
 * Both are `silent`, so they never intercept a hover meant for a point, and
 * both are omitted entirely when their inputs are absent — an empty group or an
 * unplaceable endpoint draws nothing rather than a degenerate marker at the
 * origin.
 *
 * There is deliberately NO enclosing shape for the group; see `groupCentroid`
 * for why one cannot be honest here. Membership is the green outline on each
 * point in `chartOption`.
 */
const backdrop = computed<SeriesOption[]>(() => {
  const out: SeriesOption[] = []
  const centroid = groupCentroid.value

  // The centre of gravity, as its own series ABOVE the scatter (z: 3) — a
  // tightly-matched group puts its centre exactly where the points are, and at
  // any lower z the marker is invisible under them.
  //
  // Drawn because the 튜닝 목표 table quotes this point as a coordinate: a
  // table that says "move to the group centre" is only readable if the reader
  // can see where that is. A crosshair rather than a filled symbol so it is
  // never mistaken for a tool, and each stroke is laid twice — once wide in
  // the card's own background colour, once narrow in the group green — so it
  // stays legible over a symbol as well as over empty canvas.
  if (centroid) {
    out.push({
      type: 'custom',
      silent: true,
      z: 3,
      // One datum, one renderItem call. The shape is computed in PIXELS on
      // every render rather than baked once, which is what keeps it aligned
      // through the host ResizeObserver's re-layout.
      data: [[centroid.cx, centroid.cy]],
      renderItem: (_params: unknown, api: unknown) => {
        const { coord } = api as { coord: (d: number[]) => number[] }
        const centre = coord([centroid.cx, centroid.cy])
        const cx = centre[0] ?? 0
        const cy = centre[1] ?? 0
        const arm = 7
        const stroke = (wide: boolean) => [
          {
            type: 'line' as const,
            shape: { x1: cx - arm, y1: cy, x2: cx + arm, y2: cy },
            style: { stroke: wide ? surface.value.surface : SK_STATE.ok, lineWidth: wide ? 4 : 1.75 }
          },
          {
            type: 'line' as const,
            shape: { x1: cx, y1: cy - arm, x2: cx, y2: cy + arm },
            style: { stroke: wide ? surface.value.surface : SK_STATE.ok, lineWidth: wide ? 4 : 1.75 }
          }
        ]
        // No caption on the marker. It carried one, and a group tight enough
        // to be worth reading is exactly the case where its centre lands in
        // the middle of the cluster — where the text overlapped two eqp_id
        // labels. Those go through `labelLayout` and a custom series' children
        // cannot join that pass, so the collision had no fix at this altitude.
        // The captions under the chart and on the 튜닝 목표 card both name it.
        return { type: 'group', children: [...stroke(true), ...stroke(false)] }
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
      lineStyle: { color: SK_STATE.bad, width: 1.5, type: 'solid', opacity: 0.9 },
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
    splitLine: { lineStyle: { color: sk.value.muted, opacity: 0.25, type: 'solid' as const } }
  })

  return {
    // Equal insets on all four sides, so the square box yields a square plot
    // area and the shared axis domain really is drawn at one scale.
    grid: { top: 20, right: 20, bottom: 20, left: 20 },
    // Wheel to zoom, drag to pan. One component per axis, and BOTH must be
    // present: ECharts applies one scale factor to every dataZoom a wheel event
    // reaches, so with the two axes on one shared domain (see `domain`) they
    // keep an equal span and the map stays square through any zoom. Zooming a
    // single axis would stretch the picture and silently misstate every
    // distance on a chart whose entire content is distance.
    //
    // `filterMode: 'none'` is load-bearing, not a default worth changing: the
    // default filters data outside the window OUT of the series, which would
    // take the centroid marker and the blocked-pair connector off the chart as
    // soon as their coordinates left the view. Nothing is dropped, only clipped.
    //
    // No reset control, because scrolling back out is one: ECharts clamps the
    // window at the full 0–100%, so a wheel-out always lands on the whole map.
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      { type: 'inside', yAxisIndex: 0, filterMode: 'none' }
    ],
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const { name, value } = (p as { data: FleetDatum }).data
        return `${labelFor(name)}<br/>최근접 ${unit(value[3])}`
          + `<br/>Score(평균) ${unit(value[2])}`
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
          color: p.nearest > threshold.value ? SK_STATE.bad : sk.value.series,
          // Membership, as a green OUTLINE on the point itself — the only
          // honest place for it, because the fold that decides it does not run
          // in this space (see `groupCentroid`). Blue is not membership: it
          // says only that SOME partner is inside the tolerance, so a tool can
          // be blue, sit near the centroid, and still be outside the group.
          // That is the case the old enclosing circle silently mis-stated.
          ...(groupSet.value.has(p.eqp_id)
            ? { borderColor: SK_STATE.ok, borderWidth: 2 }
            : {}),
          // Selection uses an ink outline; group membership is also named in Targets.
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

const clickable = computed(() => map.value.points.map(p => ({ x: p.x, y: p.y, item: p.eqp_id })))
useEchart(el, chartOption, {
  exportName: 'tttm-fleet-map',
  onGridClick: (detail) => {
    const tool = nearestPoint(clickable.value, detail, { maxDistancePx: 18 })
    emit('update:pickedTool', tool === props.pickedTool ? null : tool)
  }
})
</script>
