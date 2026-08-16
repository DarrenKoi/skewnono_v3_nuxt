<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="`${toolLabel} · ${fab}`"
      title="PM 튜닝"
      subtitle="하드웨어를 만질 기회는 PM 창뿐입니다 — 그때 N배화 그룹에 맞춰 튜닝할 목표를 셀 단위로 제시합니다. N이 커질수록 서로 대체 측정할 수 있는 장비가 늘어납니다."
      cadence="1주 윈도우"
      :as-of="asOf"
      :stats="metaStats"
    />

    <AppLoadingState
      v-if="pending"
      title="Fleet 데이터를 불러오는 중입니다."
    />
    <div
      v-else-if="!payload?.available"
      class="text-sm text-(--sk-bad)"
    >
      {{ payload?.summary ?? '데이터가 없습니다.' }}
    </div>

    <div
      v-else
      class="grid items-start gap-3 xl:grid-cols-[392px_minmax(0,1fr)]"
    >
      <!-- 조작 레일 — TTTM 과 같은 규칙: 레일에는 결과가 없고, 결과 쪽에는
           컨트롤이 없습니다. 이 페이지의 컨트롤은 "어느 장비를 튜닝하는가"
           하나뿐이고, 그룹의 정의(장비 선택·recipe·tolerance)는 TTTM 페이지의
           저장된 설정을 그대로 읽습니다 — 두 실험실 페이지가 서로 다른 그룹을
           말하기 시작하면 어느 쪽도 믿을 수 없게 됩니다. -->
      <div class="flex flex-col gap-3 xl:sticky xl:top-2">
        <EbeamPmTuneToolPicker
          :rows="pickerRows"
          :picked="picked"
          @update:picked="picked = $event"
        />

        <div class="rounded-[var(--sk-r-card)] border border-(--sk-border) bg-(--sk-muted-surface) px-4 py-3.5">
          <p class="sk-title">
            이 장비는
          </p>
          <p class="mt-1.5 sk-meta leading-relaxed">
            <template v-if="!primary">
              그룹이 없어 판정할 수 없습니다.
            </template>
            <template v-else-if="report?.inGroup">
              1차 그룹 <span class="sk-value-num">{{ primary.n }}</span>대의 구성원 — 유지가 목표.
            </template>
            <template v-else-if="report">
              미충족 셀 <span class="sk-value-num">{{ blockedCellCount }}</span>개 ·
              최대 조정 <span class="sk-value-num">{{ maxRequiredNm.toFixed(3) }}</span> nm
              → 진입 시 그룹 <span class="sk-value-num">{{ primary.n }}→{{ primary.n + 1 }}</span>대.
            </template>
          </p>
          <p class="mt-1.5 sk-field-label leading-relaxed">
            그룹 기준(장비 선택·recipe·tolerance)은 TTTM 페이지의 설정을 따릅니다.
          </p>
        </div>
      </div>

      <!-- 결과 — 지도·목표 → gate → 다음 후보 순. -->
      <div class="flex min-w-0 flex-col gap-3">
        <div class="grid gap-3 2xl:grid-cols-2">
          <EbeamTttmFleetMap
            :fleet="visibleFleet"
            :tools="visibleTools"
            :tolerance-index="toleranceIndex"
            :group-tools="primary?.tools"
            :blocked-pair="blockedPair"
            :picked-tool="picked"
            :halo-label="haloLabel"
          />
          <!-- File is pmTune/Targets.vue, NOT pmTune/TuneTargets.vue: Nuxt's
               auto-import collapses the repeated word at the segment boundary
               (PmTune + TuneTargets -> PmTuneTargets), so the longer file name
               would leave this tag rendering silently empty. -->
          <EbeamPmTuneTargets
            :report="report"
            :has-group="primary !== null"
            :tools="labelRefs"
            :picked-label="pickedLabel"
          />
        </div>

        <div class="grid items-stretch gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
          <EbeamPmTuneGateCard
            :gate="pickedGate"
            :picked-label="pickedLabel"
          />
          <EbeamPmTuneFocusRanking
            :tools="pmTools"
            :beam-conditions="beamConditions"
            :focus-n="focusN"
            :threshold="threshold"
            :picked="picked"
            @update:focus-n="focusN = $event"
            @update:threshold="setThreshold"
            @pick="picked = $event"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { usePmPlanningApi, type FleetResponse } from '~/composables/usePmPlanningApi'
import { preferredMatrix, type FleetToday } from '~/composables/useTttmApi'
import { admissionReport, pickDefaultTool } from '~/utils/pmTune'
import { alignSkewMatrix, groupFromCells, pickPrimary, type GroupCell, type NbaGroup } from '~/utils/tttmGrouping'
import { applyTolerance, excludedTools, scoreCells, type CellInput } from '~/utils/tttmCells'
import { fractionOfLimit, MONITOR_WAFER_CD_NM } from '~/utils/tttmLimits'
import { resolveSelection, subsetSkewMatrix, rebaseDeviations } from '~/utils/tttmFleetSubset'
import type { BeamCondition } from '~/utils/pmPlanning'

const props = defineProps<{ fab: string, toolLabel: string, toolType: string }>()

// The group's inputs are TTTM's persisted settings, read-only here — this page
// adds exactly one control (the picked tool) on top of them.
const settings = useTttmSettings()
const scoped = computed(() => settings.read(props.toolType, props.fab))

const { useTttmCheck } = useTttmApi()
const { data: payload, pending: tttmPending } = useTttmCheck(props.toolType, props.fab, () => scoped.value.recipeId)

// The gate/PM half, from pm_planning. Independent request: a slow gate payload
// must not delay the map, and vice versa.
const { fetchPmPlanningFleet } = usePmPlanningApi()
const { data: pmFleet, pending: pmPending } = useAsyncData<FleetResponse | null>(
  `pm-tune:${props.fab || 'NONE'}`,
  () => props.fab ? fetchPmPlanningFleet(props.fab) : Promise.resolve(null)
)

const pending = computed(() => tttmPending.value || pmPending.value)
const pmTools = computed(() => pmFleet.value?.tools ?? [])

const allToolIds = computed(() => (payload.value?.tools ?? []).map(t => t.eqp_id))
const selection = computed(() => resolveSelection(allToolIds.value, scoped.value.tools))

const picked = ref<string | null>(null)

// The working basis: TTTM's selection, plus the picked tool when the user
// picked one the TTTM page had deselected — its admission question is exactly
// what this page exists to answer, so it must be in the matrices.
const basis = computed(() => {
  const p = picked.value
  if (!p || !allToolIds.value.includes(p) || selection.value.includes(p)) return selection.value
  return [...selection.value, p]
})

const visibleTools = computed(() =>
  (payload.value?.tools ?? []).filter(t => basis.value.includes(t.eqp_id))
)
const labelRefs = computed(() => visibleTools.value.map(t => ({ eqp_id: t.eqp_id, label: t.label })))

const cellInputs = computed<CellInput[]>(() =>
  (payload.value?.occupied_cells ?? []).flatMap((c) => {
    const matrix = preferredMatrix(c)
    if (!matrix) return []
    return [{
      cell_id: c.cell_id,
      beam_condition: c.beam_condition,
      axis: c.axis,
      median_cd_nm: c.median_cd_nm,
      tier: c.tier,
      confidence: c.confidence,
      labels: c.labels,
      // ALIGNED on one shared basis — same invariant as TttmView: the fold and
      // the admission report walk cells by positional index.
      matrix: alignSkewMatrix(matrix, basis.value)
    }]
  })
)

const visibleFleet = computed<FleetToday>(() => ({
  matrix: subsetSkewMatrix(payload.value?.fleet_today.matrix ?? { tools: [], values: [] }, basis.value),
  consensus_deviation: rebaseDeviations(payload.value?.fleet_today.consensus_deviation ?? [], basis.value),
  median_cd_nm: payload.value?.fleet_today.median_cd_nm ?? null
}))

// No tolerance knob on this page: the server's current tolerance IS the one the
// TTTM page opens on, so the group here matches the group there by default.
const toleranceIndex = computed(() =>
  fractionOfLimit(payload.value?.current_tolerance ?? 0.05, MONITOR_WAFER_CD_NM)
)

const scoredCells = computed(() => scoreCells(cellInputs.value))
const rankedCells = computed(() => applyTolerance(scoredCells.value, toleranceIndex.value))

const groupCells = computed<GroupCell[]>(() =>
  scoredCells.value.map(c => ({
    tier: c.cell.tier,
    confidence: c.cell.confidence,
    matrix: c.matrix,
    cdNm: c.cd.nm
  }))
)
const groups = computed<NbaGroup[]>(() =>
  groupFromCells(groupCells.value, toleranceIndex.value).filter(g => g.n >= 2)
)
const primary = computed(() => pickPrimary(groups.value))

const excluded = computed(() =>
  excludedTools(basis.value, primary.value?.tools ?? [], rankedCells.value)
)

// Default pick: the tool freshest out of PM (its tuning window is now), then
// the worst-excluded tool, then the roster head — see pickDefaultTool.
//
// Gated on the pm payload having ARRIVED: the two requests race, and running
// the default off the tttm payload alone would pick the excluded-tool fallback
// and then stick with it (a set pick is never overwritten) even though the PM
// dates the rule actually wants were a moment away.
watch([pmFleet, excluded], () => {
  if (!pmFleet.value) return
  if (picked.value && pmTools.value.some(t => t.eqp_id === picked.value)) return
  picked.value = pickDefaultTool(
    pmTools.value.map(t => ({ eqp_id: t.eqp_id, post_pm_at: t.gate.post_pm_at })),
    excluded.value.map(e => e.eqp_id)
  )
}, { immediate: true })

const report = computed(() =>
  picked.value ? admissionReport(picked.value, primary.value?.tools ?? [], rankedCells.value) : null
)

const blockedCellCount = computed(() =>
  report.value?.cells.filter(row => !row.admitted).length ?? 0
)
const maxRequiredNm = computed(() =>
  Math.max(0, ...(report.value?.cells.map(row => row.requiredNm) ?? []))
)

// The map annotates the PICKED tool's worst violating pair — the same pair the
// tuning card leads with, so the two surfaces cannot argue about different
// numbers. Drawn only when it actually breached (same rule as TttmView).
const blockedPair = computed(() => {
  const lead = report.value?.cells[0]
  return lead?.worst && lead.worst.skewNm > lead.thresholdNm ? lead.worst : null
})

const haloLabel = computed(() => {
  const group = primary.value
  if (!group || !report.value || report.value.inGroup) return undefined
  return `N배화 그룹 · ${group.n}대 → ${group.n + 1}대 (튜닝 시)`
})

const pickerRows = computed(() => {
  const members = new Set(primary.value?.tools ?? [])
  return pmTools.value.map(t => ({
    eqp_id: t.eqp_id,
    verdict: t.gate.verdict,
    postPmAt: t.gate.post_pm_at,
    inGroup: members.has(t.eqp_id)
  }))
})

const pickedGate = computed(() =>
  pmTools.value.find(t => t.eqp_id === picked.value)?.gate ?? null
)
const pickedLabel = computed(() => picked.value ?? '—')

// Focus-ranking knobs, seeded from the pm_planning defaults then tunable.
const beamConditions = computed<BeamCondition[]>(() => pmFleet.value?.beam_conditions ?? ['500V', '800V'])
const focusN = ref(3)
const threshold = ref<Record<string, number>>({ '500V': 0.30, '800V': 0.40 })
watch(pmFleet, (snapshot) => {
  if (!snapshot) return
  focusN.value = snapshot.defaults.focus_n
  threshold.value = { ...snapshot.defaults.advisory_threshold }
}, { immediate: true })
const setThreshold = ({ beam, value }: { beam: BeamCondition, value: number }) => {
  threshold.value = { ...threshold.value, [beam]: value }
}

const asOf = computed(() => (payload.value?.fetched_at ?? '').replace('T', ' ').slice(0, 16))
const metaStats = computed<MetaBarStat[]>(() => {
  const holdCount = pmTools.value.filter(t => t.gate.verdict === 'hold').length
  return [
    { key: 'n', label: 'N배화', value: primary.value?.n ?? 0, tone: 'ok' },
    { key: 'tools', label: '대상 장비', value: basis.value.length, tone: 'neutral' },
    { key: 'hold', label: 'Hold', value: holdCount, tone: holdCount ? 'warn' : 'neutral' }
  ]
})
</script>
