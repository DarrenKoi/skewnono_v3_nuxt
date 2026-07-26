<template>
  <div class="space-y-3">
    <div
      v-if="analysis.focusPending.value"
      class="dashboard-surface flex h-72 items-center justify-center gap-2 rounded-(--sk-r-card) sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>

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

    <!-- ── SET scope: existing focus-only X/Y view (Task 10 replaces later) ──── -->
    <template v-else>
      <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-(--sk-r-card) px-3 py-2.5">
        <span class="sk-eyebrow">X</span>
        <USelect
          v-model="paramX"
          :items="params"
          size="xs"
          class="min-w-[9rem]"
        />
        <UIcon
          name="i-lucide-x"
          class="h-3 w-3 text-(--sk-ink-subtle)"
        />
        <span class="sk-eyebrow">Y</span>
        <USelect
          v-model="paramY"
          :items="params"
          size="xs"
          class="min-w-[9rem]"
        />
      </div>

      <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <EbeamSkewvoirPanelFrame
          title="Parameter Correlation"
          :meta="`${paramX} × ${paramY}`"
          icon="i-lucide-scatter-chart"
        >
          <EbeamSkewvoirCorrelationScatter
            :rows="analysis.siteRows.value"
            :param-x="paramX"
            :param-y="paramY"
            :unit-x="unitOf(paramX)"
            :unit-y="unitOf(paramY)"
          />
        </EbeamSkewvoirPanelFrame>

        <EbeamSkewvoirPanelFrame
          v-model="distModeSet"
          title="Distribution"
          :meta="paramY"
          :toggles="['Hist', 'Box', 'Violin']"
          icon="i-lucide-bar-chart-3"
        >
          <EbeamSkewvoirDistributionChart
            :rows="analysis.siteRows.value"
            :parameter="paramY"
            :unit="unitOf(paramY)"
            :mode="distModeSet"
          />
        </EbeamSkewvoirPanelFrame>
      </div>
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

// ── SET-scope state (existing view, unchanged) ──────────────────────────────
const paramX = ref('')
const paramY = ref('')
const distModeSet = ref('Hist')

watch(params, (list) => {
  if (!list.includes(paramX.value)) paramX.value = list[0] ?? ''
  if (!list.includes(paramY.value)) paramY.value = list[1] ?? list[0] ?? ''
}, { immediate: true })

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
