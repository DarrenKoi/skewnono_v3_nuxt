<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <p class="text-xs text-(--sk-ink-subtle)">
        장비 그룹 배치도 · 서로의 skew 거리를 2D로 펼친 지도
      </p>
      <p
        class="text-[11px] tabular-nums"
        :style="{ color: stressTone }"
      >
        stress {{ map.stress.toFixed(3) }} · {{ stressVerdict }}
      </p>
    </div>

    <!-- Square by construction. Both axes share one domain (see `domain`), so
         the box has to be square too — on a wide box the same nm would be
         drawn longer horizontally than vertically and every distance on a map
         whose whole point is distance would be misread. -->
    <div
      v-if="map.points.length >= 2"
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
        class="rounded px-1.5 py-0.5 text-[11px] bg-(--sk-chip-bg) text-(--sk-chip-text)"
      >{{ labelFor(eqp) }}</span>
      <span class="text-[11px] text-(--sk-ink-subtle)">
        — 다른 장비와 겹치는 측정이 없어 거리를 정의할 수 없습니다.
      </span>
    </div>

    <p class="mt-2 text-[11px] text-(--sk-ink-subtle)">
      축에는 단위가 없습니다. <strong>점 사이의 거리만</strong> 의미가 있으며, 회전·반전해도
      같은 지도입니다. 점 크기는 나머지 장비까지의 평균 skew(Score)이고, 빨강은
      가장 가까운 장비마저 허용오차 {{ tolerance.toFixed(3) }} nm 밖이라
      어느 N배화 그룹에도 들어가지 못하는 장비입니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { fleetMap } from '~/utils/fleetMap'
import { SK_STATE } from '~/utils/chartPalette'
import type { FleetToday, ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  fleet: FleetToday
  tools: ToolRef[]
  tolerance: number
}>()

const el = ref<HTMLDivElement | null>(null)
const sk = useChartPalette()

const map = computed(() => fleetMap(props.fleet.matrix))

const labelFor = (eqp: string) => props.tools.find(t => t.eqp_id === eqp)?.label ?? eqp

// Stress-1 reading, on the conventional Kruskal bands. Said out loud because a
// 2D map of non-Euclidean distances can be badly wrong while still looking
// tidy, and the reader has no other cue that it is.
const stressVerdict = computed(() => {
  const s = map.value.stress
  if (s < 0.05) return '거리 재현 우수'
  if (s < 0.10) return '양호'
  if (s < 0.20) return '보통 — 위치는 참고만'
  return '나쁨 — 아래 쌍별 행렬을 보십시오'
})
const stressTone = computed(() => {
  const s = map.value.stress
  if (s < 0.10) return 'var(--sk-ink-subtle)'
  return s < 0.20 ? 'var(--sk-ink-muted)' : 'var(--sk-bad)'
})

// One square domain shared by both axes. MDS distances are only readable if the
// two axes are on the SAME scale — letting ECharts fit each axis independently
// would stretch one direction and silently misstate every gap on the chart.
const domain = computed(() => {
  const xs = map.value.points.map(p => p.x)
  const ys = map.value.points.map(p => p.y)
  if (!xs.length) return { min: -1, max: 1 }
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2
  const half = Math.max(
    Math.max(...xs) - Math.min(...xs),
    Math.max(...ys) - Math.min(...ys)
  ) / 2 || 0.1
  const pad = half * 1.35
  return {
    min: Math.min(cx, cy) - pad,
    max: Math.max(cx, cy) + pad
  }
})

const chartOption = computed<EChartsOption>(() => {
  const points = map.value.points
  const maxScore = Math.max(...points.map(p => p.score), 1e-9)

  return {
    // Equal insets on all four sides, so the square box yields a square plot
    // area and the shared axis domain really is drawn at one scale.
    grid: { top: 20, right: 20, bottom: 20, left: 20 },
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const d = (p as { data: { name: string, value: [number, number, number, number] } }).data
        return `${labelFor(d.name)}<br/>최근접 ${d.value[3].toFixed(3)} nm`
          + `<br/>Score(평균) ${d.value[2].toFixed(3)} nm`
      }
    },
    xAxis: {
      type: 'value',
      min: domain.value.min,
      max: domain.value.max,
      axisLabel: { show: false },
      splitLine: { lineStyle: { color: sk.value.muted, opacity: 0.25 } }
    },
    yAxis: {
      type: 'value',
      min: domain.value.min,
      max: domain.value.max,
      axisLabel: { show: false },
      splitLine: { lineStyle: { color: sk.value.muted, opacity: 0.25 } }
    },
    series: [{
      type: 'scatter',
      data: points.map(p => ({
        name: p.eqp_id,
        value: [p.x, p.y, p.score, p.nearest],
        // Red = this tool has NO partner inside the tolerance, so it cannot join
        // any N배화 group. Compared against `nearest` rather than `score`
        // because the tolerance is a pairwise spec — see FleetPoint.nearest.
        itemStyle: { color: p.nearest > props.tolerance ? SK_STATE.bad : sk.value.series }
      })),
      // Area, not radius, tracks the score — a radius-encoded circle overstates
      // a large value by its square.
      symbolSize: (v: unknown) => {
        const score = (v as [number, number, number, number])[2]
        return 12 + Math.sqrt(score / maxScore) * 22
      },
      label: {
        show: true,
        position: 'bottom',
        distance: 6,
        formatter: (p: unknown) => labelFor((p as { data: { name: string } }).data.name),
        color: sk.value.ink,
        fontSize: 11
      },
      // A tightly-matched group is a tight CLUSTER by construction, so its
      // labels collide exactly where the map is most worth reading. Shift them
      // apart rather than hiding any — a dropped label reads as a tool that is
      // not in the fleet at all. No visible effect on the 5-tool mock, where
      // the points are already far enough apart; it is the 10-12 tool fleets
      // the office actually runs that need it.
      labelLayout: { moveOverlap: 'shiftY', hideOverlap: false }
    }]
  }
})

useEchart(el, chartOption, { exportName: 'tttm-fleet-map' })
</script>
