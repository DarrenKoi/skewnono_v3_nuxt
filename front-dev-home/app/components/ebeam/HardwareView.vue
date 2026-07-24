<script setup lang="ts">
import type { Fab } from '~/stores/navigation'
import type { SemListRow } from '~/composables/useSemListApi'
import type { HardwareMetricTone, HardwareMetricValue, HardwarePayload, HardwareServiceKey, HardwareToolType } from '~/composables/useHardwareApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { parseBmPmEvents, type BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  // Hardware services only exist for CD-SEM / HV-SEM, so the prop is the
  // narrow HardwareToolType — this is also what fetchService() requires.
  toolType: HardwareToolType
}>()

// 분기(quarterly): reference-wafer / PM-tied checks. 데일리(daily): high-cadence
// chamber-stub monitors. Same beam-quality condition, different sample & cadence.
type HardwareCategory = '분기' | '데일리'

type HardwareService = {
  key: HardwareServiceKey
  label: string
  title: string
  description: string
  icon: string
  category: HardwareCategory
}

// Daily checks lead the pill row and seed the default tab because they are the
// most frequently reviewed hardware signals.
const hardwareServices: HardwareService[] = [
  { key: 'fdc', label: 'FDC', title: 'Fault Detection & Classification', description: '실시간 fault signal, alarm trend, classification 상태를 장비 단위로 확인합니다.', icon: 'i-lucide-activity', category: '데일리' },
  { key: 'sharpness', label: 'Sharpness', title: 'Beam Sharpness (Chamber Stub)', description: 'Chamber stub 샘플로 6~8시간 주기 자동 측정한 빔 품질을 모니터링합니다.', icon: 'i-lucide-focus', category: '데일리' },
  { key: 'bm-pm', label: 'BM/PM', title: 'BM / PM Information', description: '장비별 BM 이력, PM 일정, maintenance window를 함께 확인합니다.', icon: 'i-lucide-wrench', category: '분기' },
  { key: 'bsm', label: 'BSM', title: 'Beam Shape Matching', description: 'Beam Shape 상태와 추이를 모니터링합니다.', icon: 'i-lucide-radar', category: '분기' },
  { key: 'reso-center', label: 'Reso Center', title: 'Resolution Center', description: 'Resolution center drift와 BestReso·ResoIScenter 추세를 beam condition별로 추적합니다.', icon: 'i-lucide-crosshair', category: '분기' },
  { key: 'mdc', label: 'MDC', title: 'Meas Data Correction', description: '장비별 MDC 보정값을 비교하여 tool-to-tool skew를 확인합니다.', icon: 'i-lucide-grid-3x3', category: '분기' },
  { key: 'sce', label: 'SCE', title: 'Sharpness Characteristic Equalizer', description: 'SCE 설정값과 Coefficient 곡선을 sibling 장비와 비교합니다.', icon: 'i-lucide-spline', category: '분기' }
]
const defaultHardwareService = hardwareServices[0]!

// Two labeled pill clusters in the segment bar (데일리 / 분기).
const serviceGroups: { category: HardwareCategory, services: HardwareService[] }[] = [
  { category: '데일리', services: hardwareServices.filter(s => s.category === '데일리') },
  { category: '분기', services: hardwareServices.filter(s => s.category === '분기') }
]

const { filterRows } = useSemListApi()
const { data: allRows } = await useSemList()
const { selectedToolId: storeSelectedToolId, setSelectedTool } = useNavigation()
const { fetchService } = useHardwareApi()

const route = useRoute()

// Deep-link contract (spec §4): /ebeam/cd-sem/<fab>/hardware?eqp_id=&start=&end=
// Pre-select the tool and set the time window from the URL on first load.
const qp = (k: string): string => {
  const v = route.query[k]
  return Array.isArray(v) ? (v[0] ?? '') : (v ?? '')
}
const deepLinkEqpId = qp('eqp_id')

// 30-day default window when start/end omitted (spec §3, §13).
const DAY_MS = 86_400_000
const defaultEnd = new Date()
const defaultStart = new Date(defaultEnd.getTime() - 30 * DAY_MS)
const toIso = (d: Date) => d.toISOString()
const windowStart = ref(qp('start') || toIso(defaultStart))
const windowEnd = ref(qp('end') || toIso(defaultEnd))

// Section tab is page-scoped state so navigating away and back keeps the last
// view (DESIGN.md handoff RULE 5). The list rail filters/search stay local —
// they're per-visit scratch, not worth persisting.
const activeService = useState<HardwareServiceKey>('hw-section', () => defaultHardwareService.key)
const modelFilter = ref('all')
const availabilityFilter = ref<'all' | 'On' | 'Off'>('all')
const toolSearch = ref('')
const selectedToolId = ref(deepLinkEqpId || storeSelectedToolId.value)

// Clear after consume so the store doesn't override later in-page picks on this visit.
if (storeSelectedToolId.value) {
  setSelectedTool('')
}

const rows = computed<SemListRow[]>(() => filterRows(allRows.value ?? [], props.toolType, props.fab))

const onlineCount = computed(() => rows.value.filter(row => row.available === 'On').length)

// Fab/scope rides in the mono eyebrow; the <h1> stays the fixed page name
// (DESIGN.md §7.8). ON count is read-only — list filtering lives in the rail.
const identity = computed(() => `${props.toolLabel} · ${props.fab || '—'}`)

const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'online', label: '장비 ON', value: onlineCount.value, tone: 'ok' },
  { key: 'total', label: '전체', value: rows.value.length, tone: 'neutral' }
])

const modelOptions = computed(() => [
  { label: 'All Models', value: 'all' },
  ...Array.from(new Set(rows.value.map(row => row.eqp_model_cd)))
    .sort((left, right) => left.localeCompare(right))
    .map(model => ({ label: model, value: model }))
])

const matchesQuery = (row: SemListRow) => {
  const query = toolSearch.value.trim().toLowerCase()
  if (query.length === 0) return true
  return [row.eqp_id, row.eqp_model_cd, row.eqp_ip, row.vendor_nm, row.available]
    .some(value => value.toLowerCase().includes(query))
}

const matchesModel = (row: SemListRow) =>
  modelFilter.value === 'all' || row.eqp_model_cd === modelFilter.value

// Availability segment counts respect the active search + model filter so the
// chips reflect exactly what clicking each one would reveal.
const availabilityCounts = computed(() => {
  let on = 0
  let off = 0
  for (const row of rows.value) {
    if (!matchesQuery(row) || !matchesModel(row)) continue
    if (row.available === 'On') on++
    else off++
  }
  return { all: on + off, On: on, Off: off }
})

const searchedRows = computed(() =>
  rows.value.filter(row =>
    matchesModel(row)
    && matchesQuery(row)
    && (availabilityFilter.value === 'all' || row.available === availabilityFilter.value)
  )
)

const selectedTool = computed(() =>
  rows.value.find(row => row.eqp_id === selectedToolId.value)
  ?? searchedRows.value[0]
  ?? rows.value[0]
  ?? null
)

const activeServiceDetail = computed<HardwareService>(() =>
  hardwareServices.find(service => service.key === activeService.value) ?? defaultHardwareService
)

const selectTool = (eqpId: string) => {
  selectedToolId.value = eqpId
}

const resetListControls = () => {
  toolSearch.value = ''
  modelFilter.value = 'all'
  availabilityFilter.value = 'all'
}

const hasActiveListControls = computed(() =>
  toolSearch.value.length > 0 || modelFilter.value !== 'all' || availabilityFilter.value !== 'all'
)

// Keep a valid selection when the list filters change: if the current pick
// drops out of view, fall back to the first remaining row.
watch(searchedRows, (nextRows) => {
  if (nextRows.length === 0) {
    selectedToolId.value = ''
    return
  }

  const [firstRow] = nextRows
  if (firstRow && !nextRows.some(row => row.eqp_id === selectedToolId.value)) {
    selectedToolId.value = firstRow.eqp_id
  }
}, { immediate: true })

// Cache key scopes the data ref to this view, but the key string is
// evaluated once at setup — prop changes must come through `watch` to
// trigger refetches.
const { data: servicePayload, pending: servicePending, error: serviceError } = await useAsyncData<HardwarePayload | null>(
  `hardware:${props.toolType}:${props.fab}`,
  () => fetchService({
    toolType: props.toolType,
    service: activeService.value,
    eqpId: selectedTool.value?.eqp_id,
    fabName: selectedTool.value?.fab_name,
    start: windowStart.value,
    end: windowEnd.value
  }),
  {
    watch: [() => props.toolType, () => props.fab, activeService, () => selectedTool.value?.eqp_id]
  }
)

// ---- BM/PM overlay (spec Part B) ----
// Tabs whose charts have a time x-axis; the toggle only shows there.
const OVERLAY_SERVICES: HardwareServiceKey[] = ['bsm', 'reso-center', 'mdc', 'fdc', 'sharpness']
// Page-scoped like `hw-section`: keeps its state across tab switches/visits.
const showBmPmOverlay = useState('hw-bmpm-overlay', () => true)
const overlayToggleVisible = computed(() => OVERLAY_SERVICES.includes(activeService.value))

// Second cached fetch of the existing bm-pm endpoint — events for whatever
// tab is active. Failure/empty just means no markers; charts are unaffected.
const { data: bmPmPayload } = await useAsyncData<HardwarePayload | null>(
  `hardware:bmpm-events:${props.toolType}:${props.fab}`,
  () => {
    const eqpId = selectedTool.value?.eqp_id
    if (!eqpId) return Promise.resolve(null)
    return fetchService({
      toolType: props.toolType,
      service: 'bm-pm',
      eqpId,
      fabName: selectedTool.value?.fab_name,
      start: windowStart.value,
      end: windowEnd.value
    })
  },
  { watch: [() => props.toolType, () => props.fab, () => selectedTool.value?.eqp_id] }
)

const overlayEvents = computed<BmPmEvent[]>(() =>
  showBmPmOverlay.value ? parseBmPmEvents(bmPmPayload.value?.tables ?? []) : []
)

// ---- Multi-tool comparison (MDC/SCE) ----
// Page-scoped picked set, shared with the MDC & SCE panels. The primary tool's
// sibling cohort changes when you switch tools, so clear the picks on switch —
// the panels also prune defensively against their own settings keys.
const compareIds = useState<string[]>('hw-compare-tools', () => [])
watch(() => selectedTool.value?.eqp_id, () => {
  compareIds.value = []
})

// SCE compares from `settings` already in the payload; MDC 시계열 needs each
// picked tool's own history, so fetch their mdc docs on demand.
const { data: compareMdcDocs } = await useAsyncData<Record<string, Record<string, unknown>[]>>(
  `hardware:mdc-compare:${props.toolType}:${props.fab}`,
  async () => {
    if (activeService.value !== 'mdc' || compareIds.value.length === 0) return {}
    const ids = [...compareIds.value]
    const results = await Promise.all(ids.map(id =>
      fetchService({
        toolType: props.toolType,
        service: 'mdc',
        eqpId: id,
        fabName: selectedTool.value?.fab_name,
        start: windowStart.value,
        end: windowEnd.value
      })
        .then(payload => [id, payload.docs ?? []] as const)
        .catch(() => [id, [] as Record<string, unknown>[]] as const)
    ))
    return Object.fromEntries(results)
  },
  {
    default: () => ({}),
    watch: [activeService, compareIds, () => selectedTool.value?.eqp_id, windowStart, windowEnd]
  }
)

// The backend "동일 fab 장비 · N대" card is redundant on MDC/SCE now that the
// comparison picker carries that count, so drop it from the metric-card row.
const visibleCards = computed(() => {
  const cards = servicePayload.value?.cards ?? []
  return (activeService.value === 'mdc' || activeService.value === 'sce')
    ? cards.filter(card => card.key !== 'sibling_count')
    : cards
})

const formatMetricValue = (value: HardwareMetricValue | undefined) => {
  if (value === undefined || value === null || value === '') return '-'
  return String(value)
}

const metricToneClass = (tone: HardwareMetricTone = 'neutral') => ({
  ok: 'text-emerald-700 dark:text-emerald-300',
  warning: 'text-amber-700 dark:text-amber-300',
  bad: 'text-rose-700 dark:text-rose-300',
  neutral: 'text-(--sk-ink)'
})[tone]
</script>

<template>
  <div class="min-w-0 w-full space-y-4">
    <!-- ===== Page meta bar — fixed title + scope eyebrow + ON/전체 stats ===== -->
    <EbeamMetaBar
      :eyebrow="identity"
      title="H/W 관리"
      subtitle="등록된 장비들의 Hardware 상태를 확인합니다."
      cadence="4시간 주기"
      :stats="metaStats"
    />

    <!-- ===== 2-column body: list rail + detail ===== -->
    <div class="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <!-- LEFT · search + equipment list -->
      <UCard
        class="dashboard-surface flex max-h-[36rem] flex-col overflow-hidden rounded-2xl lg:max-h-[calc(100vh-13rem)]"
        :ui="{ body: 'flex min-h-0 flex-1 flex-col p-0 sm:p-0', header: 'shrink-0 p-0 sm:px-0' }"
      >
        <template #header>
          <div class="space-y-2.5 border-b border-zinc-200/70 px-3 py-3 dark:border-zinc-800/70">
            <UInput
              v-model="toolSearch"
              size="md"
              icon="i-lucide-search"
              color="neutral"
              variant="subtle"
              placeholder="장비 ID, Model, IP 검색"
              class="w-full"
            />
            <USelect
              v-model="modelFilter"
              size="md"
              color="neutral"
              variant="subtle"
              :items="modelOptions"
              class="w-full"
            />
            <div class="flex items-center gap-1.5">
              <SkChip
                size="sm"
                :active="availabilityFilter === 'all'"
                :count="availabilityCounts.all"
                @click="availabilityFilter = 'all'"
              >
                All
              </SkChip>
              <SkChip
                size="sm"
                :active="availabilityFilter === 'On'"
                :count="availabilityCounts.On"
                @click="availabilityFilter = 'On'"
              >
                On
              </SkChip>
              <SkChip
                size="sm"
                :active="availabilityFilter === 'Off'"
                :count="availabilityCounts.Off"
                @click="availabilityFilter = 'Off'"
              >
                Off
              </SkChip>
              <UButton
                v-if="hasActiveListControls"
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-rotate-ccw"
                class="ml-auto"
                aria-label="리스트 필터 초기화"
                @click="resetListControls"
              />
            </div>
          </div>
        </template>

        <!-- Equipment rows — click to switch the detail pane -->
        <div class="flex-1 overflow-auto">
          <button
            v-for="row in searchedRows"
            :key="row.eqp_id"
            type="button"
            class="flex w-full items-start gap-2.5 border-b border-l-2 border-zinc-100 px-3.5 py-3 text-left transition-colors dark:border-zinc-800/60"
            :class="row.eqp_id === selectedToolId
              ? 'border-l-(--sk-ink) bg-(--sk-muted-surface)'
              : 'border-l-transparent hover:bg-zinc-50 dark:hover:bg-zinc-800/40'"
            :aria-current="row.eqp_id === selectedToolId ? 'true' : undefined"
            @click="selectTool(row.eqp_id)"
          >
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex items-center gap-2">
                <span class="min-w-0 flex-1 truncate font-mono text-[13px] font-bold text-(--sk-ink)">
                  {{ row.eqp_id }}
                </span>
                <span
                  class="inline-flex shrink-0 items-center gap-1 text-[11px] font-semibold"
                  :style="{ color: row.available === 'On' ? 'var(--sk-ok)' : 'var(--sk-ink-subtle)' }"
                >
                  <span
                    class="h-1.5 w-1.5 rounded-full"
                    :style="{ background: row.available === 'On' ? 'var(--sk-ok)' : 'var(--sk-ink-subtle)' }"
                  />
                  {{ row.available }}
                </span>
              </div>
              <div class="truncate text-[11px] text-(--sk-ink-muted)">
                {{ row.vendor_nm }} {{ row.eqp_model_cd }}
              </div>
              <div class="truncate font-mono text-[10px] text-(--sk-ink-subtle)">
                {{ row.fab_name }} · {{ row.eqp_ip }} · {{ row.version }}
              </div>
            </div>
          </button>

          <p
            v-if="searchedRows.length === 0"
            class="px-3.5 py-8 text-center sk-body"
          >
            검색·필터 조건에 맞는 장비가 없습니다.
          </p>
        </div>
      </UCard>

      <!-- RIGHT · service navigation + detail -->
      <div class="flex min-w-0 flex-col gap-3">
        <!-- Service tabs — tool details stay with the selectable rows in the left rail. -->
        <section class="dashboard-surface flex flex-wrap items-center rounded-2xl px-4 py-3">
          <!-- Segment tabs: BLACK = NAVIGATE (the detail view changes).
               Grouped into 데일리 / 분기 clusters by measurement cadence. -->
          <div
            role="tablist"
            aria-label="섹션 전환"
            class="flex flex-wrap items-end gap-x-4 gap-y-2"
          >
            <div
              v-for="group in serviceGroups"
              :key="group.category"
              class="flex flex-col gap-1"
            >
              <span class="px-0.5 sk-eyebrow">
                {{ group.category }}
              </span>
              <div class="flex overflow-hidden rounded-[10px] border border-(--sk-border)">
                <SkNavPill
                  v-for="service in group.services"
                  :key="service.key"
                  role="tab"
                  :aria-selected="activeService === service.key"
                  :label="service.label"
                  :icon="service.icon"
                  :active="activeService === service.key"
                  size="sm"
                  class="!rounded-none !border-0 !px-3.5"
                  @click="activeService = service.key"
                />
              </div>
            </div>
          </div>
        </section>

        <!-- Service detail -->
        <section class="dashboard-surface flex-1 rounded-2xl p-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="sk-heading">
                {{ activeServiceDetail.title }}
              </h2>
              <p class="mt-1 max-w-2xl sk-body">
                {{ activeServiceDetail.description }}
              </p>
            </div>
            <!-- BM/PM 수직 마커 오버레이 on/off — 시간축 차트가 있는 탭에서만 -->
            <USwitch
              v-if="overlayToggleVisible"
              v-model="showBmPmOverlay"
              size="sm"
              label="BM/PM 표시"
              class="shrink-0"
            />
          </div>

          <div class="mt-4 rounded-xl bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:bg-zinc-900/60 dark:text-zinc-300">
            <template v-if="servicePending">
              <span class="inline-flex items-center gap-2">
                <UIcon
                  name="i-lucide-loader-2"
                  class="h-4 w-4 animate-spin"
                />
                {{ activeServiceDetail.label }} 데이터를 불러오는 중...
              </span>
            </template>
            <template v-else-if="serviceError">
              <span class="text-rose-700 dark:text-rose-300">
                {{ activeServiceDetail.label }} 요청 실패: {{ serviceError.message }}
              </span>
            </template>
            <template v-else-if="servicePayload">
              <div class="flex flex-col gap-2">
                <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span
                      class="inline-flex items-center gap-1.5 text-xs font-semibold"
                      :class="servicePayload.available
                        ? 'text-emerald-700 dark:text-emerald-300'
                        : 'text-amber-700 dark:text-amber-300'"
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-current" />
                      {{ servicePayload.available ? 'Available' : 'Not available' }}
                    </span>
                    <span class="font-mono text-xs text-(--sk-ink-muted)">
                      {{ servicePayload.fetched_at }}
                    </span>
                  </div>
                  <!-- Compact metric strip (문서수 · 기준일 · 최신 측정 …) -->
                  <dl
                    v-if="visibleCards.length"
                    class="flex flex-wrap items-baseline gap-x-4 gap-y-1"
                  >
                    <div
                      v-for="card in visibleCards"
                      :key="card.key"
                      class="flex items-baseline gap-1.5"
                    >
                      <dt class="sk-eyebrow">
                        {{ card.label }}
                      </dt>
                      <dd
                        class="font-mono text-xs font-semibold tabular-nums"
                        :class="metricToneClass(card.tone)"
                      >
                        {{ formatMetricValue(card.value) }}<span
                          v-if="card.unit"
                          class="ml-0.5 font-normal text-(--sk-ink-muted)"
                        >{{ card.unit }}</span>
                      </dd>
                    </div>
                  </dl>
                </div>
                <!-- Normal payloads carry a boilerplate summary that restates the
                     tab description above; only hint/unavailable payloads (empty
                     cards) say something the header doesn't. -->
                <p v-if="!servicePayload.available || servicePayload.cards.length === 0">
                  {{ servicePayload.summary }}
                </p>

                <!-- BM/PM: dedicated past/future tables with expandable engineer notes -->
                <EbeamHardwareBmPmTables
                  v-if="activeService === 'bm-pm' && servicePayload.tables.length"
                  :tables="servicePayload.tables"
                />

                <!-- BSM: beam_condition filter + scalar trends + 360° radars (reads docs) -->
                <EbeamHardwareBsmPanel
                  v-if="activeService === 'bsm'"
                  :docs="servicePayload.docs ?? []"
                  :maintenance-events="overlayEvents"
                />

                <!-- Reso Center: drift scatter + best-reso trend + focus sweep -->
                <EbeamHardwareResoCenterPanel
                  v-else-if="activeService === 'reso-center'"
                  :docs="servicePayload.docs ?? []"
                  :maintenance-events="overlayEvents"
                />

                <!-- FDC: fdc_key sub-tabs -->
                <EbeamHardwareFdcPanel
                  v-else-if="activeService === 'fdc'"
                  :docs="servicePayload.docs ?? []"
                  :maintenance-events="overlayEvents"
                />

                <!-- Sharpness: chamber-stub beam quality — condition filter + summ_beam trends + per-degree radars -->
                <EbeamHardwareSharpnessPanel
                  v-else-if="activeService === 'sharpness'"
                  :docs="servicePayload.docs ?? []"
                  :maintenance-events="overlayEvents"
                />

                <!-- MDC: 시계열 (trajectory + per-axis trends) / 비교 sub-tabs -->
                <EbeamHardwareMdcPanel
                  v-else-if="activeService === 'mdc'"
                  :settings="servicePayload.settings ?? {}"
                  :docs="servicePayload.docs ?? []"
                  :compare-docs="compareMdcDocs ?? {}"
                  :selected-eqp="selectedTool?.eqp_id ?? ''"
                  :maintenance-events="overlayEvents"
                />

                <!-- SCE: settings compare + coefficient curve -->
                <EbeamHardwareScePanel
                  v-else-if="activeService === 'sce'"
                  :settings="servicePayload.settings ?? {}"
                  :selected-eqp="selectedTool?.eqp_id ?? ''"
                />

                <!-- Generic table renderer (excluded for all dedicated panel services) -->
                <div
                  v-for="section in (['bm-pm', 'bsm', 'reso-center', 'fdc', 'mdc', 'sce', 'sharpness'].includes(activeService) ? [] : servicePayload.tables)"
                  :key="section.key"
                  class="mt-3 overflow-hidden rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
                >
                  <div class="border-b border-(--sk-border-soft) px-3 py-2 sk-title">
                    {{ section.title }}
                  </div>
                  <div class="overflow-x-auto">
                    <table class="min-w-full text-left text-xs">
                      <thead class="bg-zinc-100 text-(--sk-ink-muted) dark:bg-zinc-900">
                        <tr>
                          <th
                            v-for="column in section.columns"
                            :key="column.key"
                            class="whitespace-nowrap px-3 py-2 sk-eyebrow"
                          >
                            {{ column.label }}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="(row, rowIndex) in section.rows"
                          :key="rowIndex"
                          class="border-t border-(--sk-border-soft)"
                        >
                          <td
                            v-for="column in section.columns"
                            :key="column.key"
                            class="whitespace-nowrap px-3 py-2 sk-value-num"
                          >
                            {{ formatMetricValue(row[column.key]) }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </template>
            <span v-else>
              <span class="font-semibold text-zinc-900 dark:text-zinc-100">{{ activeServiceDetail.label }}</span>
              정보는 선택한 장비를 기준으로 열립니다.
            </span>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
