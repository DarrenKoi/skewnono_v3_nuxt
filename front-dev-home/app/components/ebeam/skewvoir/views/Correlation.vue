<template>
  <div class="space-y-3">
    <AppLoadingState
      v-if="analysis.focusPending.value"
      variant="inline"
      class="dashboard-surface h-72 rounded-(--sk-r-card)"
      title="불러오는 중입니다."
    />

    <div
      v-else-if="!params.length"
      class="dashboard-surface flex h-72 items-center justify-center sk-body"
    >
      파라미터 데이터가 없습니다.
    </div>

    <!-- ── SINGLE scope: exact-pair factor explorer ─────────────────────────── -->
    <template v-else-if="analysis.scope.value === 'single'">
      <EbeamSkewvoirFactorQueryBuilder
        v-model="query"
        :cd-params="params"
        :fdc-params="fdcParams"
        :coordinate-ready="coordinateReady"
      />

      <EbeamSkewvoirFactorRelationshipSummary :result="relationship" />

      <!-- The pair reaches into FDC, so at home its correlation is the mock's
           shared health scalar showing through rather than a tool signal. -->
      <EbeamSkewvoirDemoDataNote v-if="query.yKind === 'fdc'" />

      <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <EbeamSkewvoirPanelFrame
          title="Paired Scatter"
          :meta="`${xLabel} × ${yLabel}`"
          icon="i-lucide-scatter-chart"
        >
          <EbeamSkewvoirCorrelationScatter
            :points="relationship.points"
            :param-x="xLabel"
            :param-y="yLabel"
            :unit-x="unitX"
            :unit-y="unitY"
            :readiness-reason="relationship.reason"
            @focus="onFocus"
          />
        </EbeamSkewvoirPanelFrame>

        <EbeamSkewvoirPanelFrame
          v-model="distMode"
          title="Marginal Distribution"
          :meta="yLabel"
          :toggles="['Hist', 'ECDF', 'Box', 'Violin']"
          icon="i-lucide-bar-chart-3"
        >
          <EbeamSkewvoirDistributionChart
            :values="marginalValues"
            :parameter="yLabel"
            :unit="unitY"
            :mode="distMode"
          />
        </EbeamSkewvoirPanelFrame>
      </div>

      <EbeamSkewvoirPanelFrame
        v-if="query.group !== 'none' && coordinateReady && groupDist.length"
        title="Group Distribution"
        :meta="query.group === 'radius' ? '반경 밴드' : '섹터'"
        icon="i-lucide-layers"
      >
        <EbeamSkewvoirDistributionChart
          :groups="groupDist"
          :unit="unitY"
          mode="Box"
        />
      </EbeamSkewvoirPanelFrame>

      <EbeamSkewvoirPanelFrame
        title="Paired Evidence"
        :meta="`${relationship.pairN} 짝 · ${relationship.missingN} 누락`"
        icon="i-lucide-table"
      >
        <EbeamSkewvoirFactorPairedEvidenceTable
          :points="relationship.points"
          :x-label="xLabel"
          :y-label="yLabel"
          :focused-site="analysis.focusedSite.value"
          @focus="onFocus"
        />
      </EbeamSkewvoirPanelFrame>

      <EbeamSkewvoirPositionSiteEvidenceDrawer
        v-model:open="drawerOpen"
        :spatial="spatial"
        :analysis="analysis"
        :unit="unitX"
      />
    </template>

    <!-- ── SET scope: Across-MSR Outcome — one MSR is one point ─────────────── -->
    <template v-else>
      <div
        v-if="!axes.length"
        class="dashboard-surface flex h-72 items-center justify-center sk-body"
      >
        비교할 측정이 아직 없습니다.
      </div>

      <template v-else>
        <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-(--sk-r-card) px-3 py-2.5">
          <span class="sk-label">X</span>
          <USelect
            v-model="axisXId"
            :items="axisItems"
            size="xs"
            class="min-w-[13rem]"
          />
          <UIcon
            name="i-lucide-x"
            class="h-3 w-3 text-(--sk-ink-subtle)"
          />
          <span class="sk-label">Y</span>
          <USelect
            v-model="axisYId"
            :items="axisItems"
            size="xs"
            class="min-w-[13rem]"
          />
        </div>

        <EbeamSkewvoirFactorAcrossMsrSummary :result="acrossMsr" />

        <EbeamSkewvoirDemoDataNote v-if="hasFdcAxis(acrossMsr)" />

        <EbeamSkewvoirPanelFrame
          title="Across-MSR Outcome"
          :meta="`MSR ${acrossMsr.points.length}건 · 장비 ${acrossMsr.strata.length}대`"
          icon="i-lucide-scatter-chart"
        >
          <EbeamSkewvoirFactorAcrossMsrScatter
            :result="acrossMsr"
            @select="analysis.setFocusedMsr"
          />
        </EbeamSkewvoirPanelFrame>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { FactorQuery } from '~/components/ebeam/skewvoir/factor/QueryBuilder.vue'
import type { DistributionGroup } from '~/components/ebeam/skewvoir/DistributionChart.vue'
import { analyzeSpatial } from '~/utils/skewvoirAnalysis/spatial'
import { isNamedParam } from '~/utils/skewvoirAnalysis/paramOrder'
import { buildCdCdRelationship, buildCdFdcRelationship } from '~/utils/skewvoirAnalysis/relationships'
import type { AcrossMsrIdentity } from '~/utils/skewvoirAnalysis/acrossMsr'
import { acrossMsrAxes, buildAcrossMsrOutcome, hasFdcAxis } from '~/utils/skewvoirAnalysis/acrossMsr'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// Named parameters only. The unnamed dummy MP is selectable as the active `mp`
// (it has images to review) but not as a correlation axis: it is a one-shot
// settling point with nothing to pair against, and the axis state uses '' to
// mean "unset" — the very conflation routeQuery's sentinel exists to avoid.
const params = computed(() => props.analysis.availableParams.value.filter(isNamedParam))
const fdcParams = computed(() => props.analysis.focusFile.value?.fdc_params.map(p => p.name) ?? [])

const unitOf = (param: string) =>
  props.analysis.paramSummaries.value.find(p => p.parameter === param)?.unit ?? ''
const fdcUnitOf = (name: string) =>
  props.analysis.focusFile.value?.fdc_params.find(p => p.name === name)?.unit ?? ''

// ── SET-scope state: Across-MSR Outcome ─────────────────────────────────────
// The row unit here is the MSR, not the site — so the axes are the per-MSR
// FEATURES (level / spread / coverage / failure / spatial / FDC), read off the
// shared feature table rather than recomputed. `analysis.featureRegistry` is the
// column dictionary; acrossMsrAxes flattens it into plottable columns.
const axes = computed(() => acrossMsrAxes(props.analysis.featureRegistry.value))
const axisItems = computed(() => axes.value.map(a => ({ label: a.label, value: a.id })))

const axisXId = ref('')
const axisYId = ref('')

// Defaults name the question this mode exists to ask: does the CD outcome move
// with a tool-side predictor? So Y is the CD level (the outcome) and X is the
// first FDC channel when the set carries one, falling back to CD spread.
watch(axes, (list) => {
  const ids = list.map(a => a.id)
  if (!ids.includes(axisYId.value)) axisYId.value = ids.includes('level') ? 'level' : (ids[0] ?? '')
  if (!ids.includes(axisXId.value)) {
    const fdc = list.find(a => a.family === 'fixed_fdc' || a.family === 'dynamic_fdc')
    axisXId.value = fdc?.id ?? (ids.find(id => id !== axisYId.value) ?? ids[0] ?? '')
  }
}, { immediate: true })

const axisById = (id: string) => axes.value.find(a => a.id === id) ?? null

// Tool + label per MSR come from the already-loaded meas_hist rows — the same
// eqp_id the Time-Series tool colors are ranked over, so one tool wears one
// color across the workspace.
const msrIdentity = computed(() => {
  const map = new Map<string, AcrossMsrIdentity>()
  for (const [msr, row] of props.analysis.rowByMsr.value) {
    map.set(msr, { eqpId: row.eqp_id, label: props.analysis.msrLabel(msr) })
  }
  return map
})

const acrossMsr = computed(() => buildAcrossMsrOutcome(
  props.analysis.featureRows.value,
  axisById(axisXId.value),
  axisById(axisYId.value),
  msrIdentity.value
))

// ── SINGLE-scope explorer state ─────────────────────────────────────────────
const distMode = ref('Hist')
const drawerOpen = ref(false)

// Seed X/Y from the URL `x`/`y` (e.g. the overview's "짝지은 값" hand-off) when
// present; the immediate watch below validates them against the loaded params
// and falls back to the first two available params otherwise (unchanged
// default behaviour when no x/y is in the URL).
const query = ref<FactorQuery>({
  yKind: 'cd',
  xParam: props.analysis.xParam.value ?? '',
  yParam: props.analysis.yParam.value ?? '',
  fdcParam: '',
  group: 'none'
})

// Keep the query valid as the focus (and thus its parameters / FDC channels)
// changes: re-seed any axis whose selection no longer exists.
watch([params, fdcParams], ([cd, fdc]) => {
  if (!cd.includes(query.value.xParam)) query.value.xParam = cd[0] ?? ''
  if (!cd.includes(query.value.yParam)) query.value.yParam = cd[1] ?? cd[0] ?? ''
  if (!fdc.includes(query.value.fdcParam)) query.value.fdcParam = fdc[0] ?? ''
  if (query.value.yKind === 'fdc' && fdc.length === 0) query.value.yKind = 'cd'
}, { immediate: true })

// Write the active X/Y pair back to the URL so the explorer stays shareable —
// a link copied mid-session reopens on the same pair (round-trips with the
// seed above).
watch([() => query.value.xParam, () => query.value.yParam], ([x, y]) => {
  if (!x) return
  props.analysis.setXY(x, y || null)
})

const unitX = computed(() => unitOf(query.value.xParam))
const unitY = computed(() =>
  query.value.yKind === 'fdc' ? fdcUnitOf(query.value.fdcParam) : unitOf(query.value.yParam)
)

// Spatial diagnosis on the X parameter — its site sequences key the pairs, so its
// coordinates place them. Drives coordinate readiness (the group gate) + the SEM
// drawer's site lookup.
const spatial = computed(() =>
  analyzeSpatial(
    props.analysis.siteRows.value,
    query.value.xParam,
    props.analysis.waferGeo.value,
    { unit: unitX.value }
  )
)
const coordinateReady = computed(() => spatial.value.readiness.coordinates === 'ok')

// Reset a stale radius/sector grouping when coordinates become unavailable.
watch(coordinateReady, (ready) => {
  if (!ready && query.value.group !== 'none') query.value.group = 'none'
})

const relationship = computed(() => {
  const rows = props.analysis.siteRows.value
  if (query.value.yKind === 'fdc') {
    return buildCdFdcRelationship(
      rows, query.value.xParam, query.value.fdcParam,
      props.analysis.focusFile.value?.dynamic_fdc ?? {}
    )
  }
  return buildCdCdRelationship(rows, query.value.xParam, query.value.yParam)
})

const xLabel = computed(() => query.value.xParam)
const yLabel = computed(() => (query.value.yKind === 'fdc' ? query.value.fdcParam : query.value.yParam))
// Marginal distribution reflects the ACTIVE query's paired Y values, not every row.
const marginalValues = computed(() => relationship.value.points.map(p => p.y))

// Group label per site sequence (from the X-param spatial placement).
const SECTOR_ORDER = ['E', 'N', 'W', 'S']
const RADIUS_ORDER = ['중심', '중간', '외곽']
const SECTOR_LABEL: Record<string, string> = { E: '우(E)', N: '상(N)', W: '좌(W)', S: '하(S)' }

const groupBySeq = computed(() => {
  const m = new Map<number, string>()
  if (query.value.group === 'sector') {
    for (const s of spatial.value.sites) if (s.sector) m.set(s.sequence, s.sector)
  } else if (query.value.group === 'radius') {
    const radii = spatial.value.sites.map(s => s.radiusMm).filter((r): r is number => r != null)
    const maxR = Math.max(...radii, 1)
    for (const s of spatial.value.sites) {
      if (s.radiusMm == null) continue
      const frac = s.radiusMm / maxR
      m.set(s.sequence, frac < 1 / 3 ? '중심' : frac < 2 / 3 ? '중간' : '외곽')
    }
  }
  return m
})

// Group distribution: the paired Y values split by the active grouping, ordered.
const groupDist = computed<DistributionGroup[]>(() => {
  if (query.value.group === 'none') return []
  const byKey = new Map<string, number[]>()
  for (const p of relationship.value.points) {
    const key = groupBySeq.value.get(p.sequence)
    if (!key) continue
    const arr = byKey.get(key) ?? []
    arr.push(p.y)
    byKey.set(key, arr)
  }
  const order = query.value.group === 'sector' ? SECTOR_ORDER : RADIUS_ORDER
  return order.flatMap((key) => {
    const values = byKey.get(key)
    if (!values || values.length === 0) return []
    const label = query.value.group === 'sector' ? (SECTOR_LABEL[key] ?? key) : key
    return [{ label, values }]
  })
})

// Scatter/table click → move the focused site + SEM preview (acceptance).
const onFocus = (chip: string) => {
  props.analysis.setFocusedSite(chip)
  const site = spatial.value.sites.find(s => s.chip === chip)
  if (site) props.analysis.setFocusedSequence(site.sequence)
  drawerOpen.value = true
}
</script>
