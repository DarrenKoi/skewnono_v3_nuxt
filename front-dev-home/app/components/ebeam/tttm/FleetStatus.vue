<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">
      오늘 장비 그룹 skew 현황
    </p>
    <div class="mt-3 space-y-2">
      <div
        v-for="d in sorted"
        :key="d.eqp_id"
        class="flex items-center gap-3 text-sm"
      >
        <span class="w-24 text-(--sk-ink-muted)">{{ labelFor(d.eqp_id) }}</span>
        <div class="flex-1 relative h-4">
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
          class="w-16 text-right tabular-nums"
          :style="{ color: overLimit(d.deviation) ? 'var(--sk-bad)' : 'var(--sk-ink)' }"
        >{{ d.deviation >= 0 ? '+' : '' }}{{ d.deviation.toFixed(3) }}</span>
      </div>
    </div>
    <p class="mt-2 text-[11px] text-(--sk-ink-subtle)">
      잔차 = tool − consensus(중앙값). 0 = 장비 그룹 합의와 일치.
      <span :style="{ color: 'var(--sk-bad)' }">빨간 선 ±{{ actionLimit.toFixed(2) }} nm</span>
      = 이 밖으로 나가면 PM/BM 대상입니다 (기준은 CD의
      {{ (PM_BM_ACTION_LIMIT_RATIO * 100).toFixed(0) }}%이며,
      <template v-if="cd.assumed">
        이 데이터에는 CD가 없어 모니터 wafer {{ cd.nm }} nm 를 가정했습니다
      </template>
      <template v-else>
        측정 CD 중앙값 {{ cd.nm.toFixed(1) }} nm 기준입니다
      </template>).
      안쪽 옅은 선
      ±{{ MEASUREMENT_FLOOR_NM.toFixed(2) }} nm 는 시험 자체의 불확도라,
      그보다 작은 차이는 구별 불가입니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import { toolLabels } from '~/utils/toolLabels'
import { actionLimitNm, resolveNominalCd, PM_BM_ACTION_LIMIT_RATIO, MEASUREMENT_FLOOR_NM } from '~/utils/tttmLimits'
import type { FleetToday, ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{ fleet: FleetToday, tools: ToolRef[] }>()

// The action limit is 1% of the CD actually measured, so this line moves with
// the recipe rather than sitting at a fixed 0.15 nm. `median_cd_nm` is nullable
// by contract; when it is null we fall back to the monitor wafer and the
// caption below says so, because a drawn-but-assumed limit that reads as
// measured is the failure this replaced.
const cd = computed(() => resolveNominalCd(props.fleet.median_cd_nm))
const actionLimit = computed(() => actionLimitNm(cd.value.nm))

// Rebuilt when the payload swaps the fleet; destructuring at setup would pin
// the first fab's labels for the life of the component.
const labels = computed(() => toolLabels(props.tools))
const labelFor = (eqp: string) => labels.value.labelFor(eqp)

// The action limit is always on the scale, so the red line cannot fall off the
// end of the track on a well-matched fleet and leave the bars looking unbounded.
const maxAbs = computed(() =>
  Math.max(
    actionLimit.value * 1.15,
    ...props.fleet.consensus_deviation.map(d => Math.abs(d.deviation))
  )
)
const sorted = computed(() =>
  [...props.fleet.consensus_deviation].sort((a, b) => a.deviation - b.deviation)
)

// Track positions (%) of a symmetric ±limit pair, measured from the centre line.
const edgesFor = (limit: number) => {
  const half = (limit / maxAbs.value) * 50
  return [50 - half, 50 + half]
}
const actionEdges = computed(() => edgesFor(actionLimit.value))
const floorEdges = computed(() => edgesFor(MEASUREMENT_FLOOR_NM))

const overLimit = (dev: number) => Math.abs(dev) > actionLimit.value

// Bar grows from the center line toward the sign direction.
const barStyle = (dev: number) => {
  const half = (Math.abs(dev) / maxAbs.value) * 50
  const bg = overLimit(dev) ? 'var(--sk-bad)' : 'var(--sk-ok)'
  return dev >= 0
    ? { left: '50%', width: `${half}%`, background: bg }
    : { right: '50%', width: `${half}%`, background: bg }
}
</script>
