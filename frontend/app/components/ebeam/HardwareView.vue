<script setup lang="ts">
import type { SemListRow } from '~/composables/useSemListApi'
import type { HardwareMetricTone, HardwareMetricValue, HardwarePayload, HardwareServiceKey, HardwareToolType } from '~/composables/useHardwareApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { parseBmPmEvents, type BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  fabs: string[]
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
  { key: 'sce', label: 'SCE', title: 'Sharpness Characteristic Equalizer', description: 'SCE 설정값과 Coefficient 곡선을 sibling 장비와 비교하고, 격일 수집 이력의 변화를 추적합니다.', icon: 'i-lucide-spline', category: '분기' }
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
// view (DESIGN.md handoff RULE 5). Search and the On/Off filter stay local —
// they're per-visit scratch, not worth persisting.
const activeService = useState<HardwareServiceKey>('hw-section', () => defaultHardwareService.key)
// The model is the page's GATE, not a filter (user decision 2026-08-25): no
// tool shows until at least one is picked, so the reader always knows which
// models the page is about. Several models may be picked together (chips
// toggle); an empty list is "not picked". Page-scoped like the section tab,
// so coming back to the page does not re-gate it.
const modelFilters = useState<string[]>('hw-models', () => [])
const modelPicked = computed(() => modelFilters.value.length > 0)
const toggleModel = (model: string) => {
  modelFilters.value = modelFilters.value.includes(model)
    ? modelFilters.value.filter(picked => picked !== model)
    : [...modelFilters.value, model]
}
const availabilityFilter = ref<'all' | 'On' | 'Off'>('all')
const toolSearch = ref('')
const selectedToolId = ref(deepLinkEqpId || storeSelectedToolId.value)

// Clear after consume so the store doesn't override later in-page picks on this visit.
if (storeSelectedToolId.value) {
  setSelectedTool('')
}

const fabsKey = computed(() => props.fabs.join(','))

const rows = computed<SemListRow[]>(() => filterRows(allRows.value ?? [], props.toolType, props.fabs))

const onlineCount = computed(() => rows.value.filter(row => row.available === 'On').length)

// Fab/scope rides in the mono eyebrow; the <h1> stays the fixed page name
// (DESIGN.md §7.8). ON count is read-only — list filtering lives in the rail.
const identity = computed(() => `${props.toolLabel} · ${props.fabs.join(' + ') || '—'}`)

const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'online', label: '장비 ON', value: onlineCount.value, tone: 'ok' },
  { key: 'total', label: '전체', value: rows.value.length, tone: 'neutral' }
])

const matchesQuery = (row: SemListRow) => {
  const query = toolSearch.value.trim().toLowerCase()
  if (query.length === 0) return true
  return [row.eqp_id, row.eqp_model_cd, row.eqp_ip, row.vendor_nm, row.available]
    .some(value => value.toLowerCase().includes(query))
}

const matchesModel = (row: SemListRow) => modelFilters.value.includes(row.eqp_model_cd)

const matchesAvailability = (row: SemListRow) =>
  availabilityFilter.value === 'all' || row.available === availabilityFilter.value

// Each chip row's counts respect the OTHER two controls (search + the other
// row), so a count is exactly what clicking that chip would reveal. A model
// chip is never dropped for counting zero: the model row is the roster of what
// this fab union owns, and a model whose tools are all Off still exists.
const modelGroups = computed(() => {
  const counts = new Map<string, number>()
  for (const row of rows.value) {
    const visible = matchesQuery(row) && matchesAvailability(row)
    counts.set(row.eqp_model_cd, (counts.get(row.eqp_model_cd) ?? 0) + (visible ? 1 : 0))
  }
  return Array.from(counts, ([model, count]) => ({ model, count }))
    .sort((left, right) => left.model.localeCompare(right.model))
})
// A deep-linked or store-handed tool names its model for the gate, so the
// link opens on that tool instead of on an empty strip. Models already
// picked stay: the link adds to the selection rather than replacing it.
const linkedModel = selectedToolId.value
  ? rows.value.find(row => row.eqp_id === selectedToolId.value)?.eqp_model_cd
  : undefined
if (linkedModel && !modelFilters.value.includes(linkedModel)) {
  modelFilters.value = [...modelFilters.value, linkedModel]
}

// A model remembered from another fab may be absent from this roster. Left in
// place it would gate the page on a choice no chip shows as active, so drop
// it and let the empty state name the real situation. `modelGroups` keeps
// zero-count models, so membership here is the roster, not the filtered view.
watch(modelGroups, (groups) => {
  const present = modelFilters.value.filter(model => groups.some(group => group.model === model))
  if (present.length !== modelFilters.value.length) modelFilters.value = present
}, { immediate: true })

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
  rows.value.filter(row => matchesModel(row) && matchesQuery(row) && matchesAvailability(row))
)

// One chip per eqp_id. sem_list repeats an id (10 of 300 mock rows; R3 lists
// ECDX729 twice — a mock artefact, ids are unique at the office), and the rail
// kept both rows because their bodies differed (IP, version). A chip carries
// only the id, and the detail is fetched BY id, so a second chip would light up
// together with the first and open the same data. The first occurrence stands
// for the id, which is also the row `selectedTool` resolves to.
const toolChips = computed(() => {
  const seen = new Set<string>()
  return searchedRows.value.filter((row) => {
    if (seen.has(row.eqp_id)) return false
    seen.add(row.eqp_id)
    return true
  })
})
// The picked models' roster size, for "N대 중 M대 표시" — the model is a gate,
// so the base is the picked models, not the fab: measured against the whole
// fab the line would read as if the other models were hidden by a filter.
const modelToolCount = computed(() =>
  new Set(rows.value.filter(matchesModel).map(row => row.eqp_id)).size
)

// Only a tool in view can be the subject; with no model picked there is none,
// and the results below say so rather than showing a tool nobody chose.
const selectedTool = computed(() =>
  searchedRows.value.find(row => row.eqp_id === selectedToolId.value) ?? null
)

const activeServiceDetail = computed<HardwareService>(() =>
  hardwareServices.find(service => service.key === activeService.value) ?? defaultHardwareService
)

const selectTool = (eqpId: string) => {
  selectedToolId.value = eqpId
}

// Reset clears the refinements, not the gate: the model is a choice the page
// is computed for, and un-picking it would empty the page under the reader.
const resetListControls = () => {
  toolSearch.value = ''
  availabilityFilter.value = 'all'
}

const hasActiveListControls = computed(() =>
  toolSearch.value.length > 0 || availabilityFilter.value !== 'all'
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
  `hardware:${props.toolType}:${props.fabs.join(',')}`,
  () => {
    // Gated: no tool, no request — the results area shows the empty state.
    const tool = selectedTool.value
    if (!tool) return Promise.resolve(null)
    return fetchService({
      toolType: props.toolType,
      service: activeService.value,
      eqpId: tool.eqp_id,
      fabName: tool.fab_name,
      start: windowStart.value,
      end: windowEnd.value
    })
  },
  {
    watch: [() => props.toolType, fabsKey, activeService, () => selectedTool.value?.eqp_id]
  }
)

// ---- BM/PM overlay (spec Part B) ----
// Tabs whose charts have a time x-axis; the toggle only shows there.
const OVERLAY_SERVICES: HardwareServiceKey[] = ['bsm', 'reso-center', 'mdc', 'fdc', 'sharpness', 'sce']
// Page-scoped like `hw-section`: keeps its state across tab switches/visits.
const showBmPmOverlay = useState('hw-bmpm-overlay', () => true)
const overlayToggleVisible = computed(() => OVERLAY_SERVICES.includes(activeService.value))

// Second cached fetch of the existing bm-pm endpoint — events for whatever
// tab is active. Failure/empty just means no markers; charts are unaffected.
const { data: bmPmPayload } = await useAsyncData<HardwarePayload | null>(
  `hardware:bmpm-events:${props.toolType}:${props.fabs.join(',')}`,
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
  { watch: [() => props.toolType, fabsKey, () => selectedTool.value?.eqp_id] }
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
  `hardware:mdc-compare:${props.toolType}:${props.fabs.join(',')}`,
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

    <!-- ===== Tool strip — which tool everything below is computed for =====
         This was a 320px list rail beside the detail. It sits above the results
         now (DESIGN.md §Layout, the scope-bar rule): the page has exactly one
         required decision — the tool — and every card and chart below is
         computed for that one tool, so the decision belongs first in reading
         order, and the detail (FDC's per-key grid, the MDC/SCE comparison
         charts) gets the full width instead of `1fr` beside a rail.

         Two chip rows, two roles. Model chips NARROW the roster, so they take
         the terracotta FILTER fill — and the model is also the page's gate:
         there is no "all models" chip, and nothing below opens until one is
         picked. The tool chip picks the one subject among peers — the ink fill
         that the rail's selected row already used, and the `tone="ink"` SkChip
         that skewvoir's ParamCoverageList uses for the same "one of these"
         choice. Different roles, so the two fills do not mix. -->
    <section class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p class="shrink-0 sk-panel-title">
          장비 선택
        </p>
        <div
          role="group"
          aria-label="모델 선택"
          class="flex flex-wrap items-center gap-1.5"
        >
          <SkChip
            v-for="group in modelGroups"
            :key="group.model"
            size="sm"
            :active="modelFilters.includes(group.model)"
            :count="group.count"
            @click="toggleModel(group.model)"
          >
            {{ group.model }}
          </SkChip>
        </div>

        <!-- Availability + search sit at the trailing edge: they refine the
             roster the model row already narrowed, rather than define it — so
             they appear with the model, not before it (three zero chips beside
             an empty strip would read as a filter that hid everything). -->
        <div
          v-if="modelPicked"
          class="ml-auto flex flex-wrap items-center gap-1.5"
        >
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
          <UInput
            v-model="toolSearch"
            size="sm"
            icon="i-lucide-search"
            color="neutral"
            variant="subtle"
            placeholder="장비 ID, Model, IP 검색"
            class="w-52"
          />
          <UButton
            v-if="hasActiveListControls"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            aria-label="리스트 필터 초기화"
            @click="resetListControls"
          />
        </div>
      </div>

      <!-- Tool chips — click to switch the detail below. `toolChips` is
           deduplicated, so the id is a safe key here (the rail keyed by
           position because it kept sem_list's repeated ids as separate rows).

           Capped at about four rows: a single fab holds up to ~20 tools of one
           type, which fits, but a multi-fab union can reach 60+, and a strip
           that tall pushes the data it exists to select below the fold. -->
      <div
        v-if="toolChips.length"
        role="group"
        aria-label="장비 선택"
        class="mt-3 flex max-h-[9.5rem] flex-wrap gap-1.5 overflow-y-auto"
      >
        <SkChip
          v-for="row in toolChips"
          :key="row.eqp_id"
          size="sm"
          tone="ink"
          :active="row.eqp_id === selectedToolId"
          :title="`${row.vendor_nm} ${row.eqp_model_cd} · ${row.fab_name} · ${row.eqp_ip} · ${row.version}`"
          @click="selectTool(row.eqp_id)"
        >
          <span class="inline-flex items-center gap-1.5 font-mono">
            <!-- On keeps the semantic green on either fill; Off rides
                 currentColor so it stays visible on the ink fill, where the
                 subtle-ink token would vanish. -->
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="row.available === 'On' ? 'bg-(--sk-ok)' : 'bg-current opacity-40'"
            />
            {{ row.eqp_id }}
          </span>
        </SkChip>
      </div>
      <p
        v-else-if="!modelPicked"
        class="mt-3 sk-body"
      >
        모델을 고르면 그 모델의 장비가 여기에 나타납니다.
      </p>
      <p
        v-else
        class="mt-3 sk-body"
      >
        검색·필터 조건에 맞는 장비가 없습니다.
      </p>

      <!-- The rail row used to carry vendor / model / fab / ip / version under
           each id; a chip cannot, so the SELECTED tool's line moves here. -->
      <p
        v-if="selectedTool"
        class="mt-2.5 flex flex-wrap items-baseline gap-x-2 sk-field-label"
      >
        <strong class="font-mono font-semibold text-(--sk-ink)">{{ selectedTool.eqp_id }}</strong>
        <span>{{ selectedTool.vendor_nm }} {{ selectedTool.eqp_model_cd }}</span>
        <span>·</span>
        <span>{{ selectedTool.fab_name }}</span>
        <span>·</span>
        <span class="font-mono">{{ selectedTool.eqp_ip }}</span>
        <span>·</span>
        <span class="font-mono">{{ selectedTool.version }}</span>
        <!-- Both numbers are data values, so both take full ink (DESIGN.md
             §Colors); only the words between them stay on the label tone. -->
        <span class="ml-auto">
          {{ modelFilters.join(' + ') }}
          <strong class="font-mono tabular-nums text-(--sk-ink)">{{ modelToolCount }}</strong>대 중
          <strong class="font-mono tabular-nums text-(--sk-ink)">{{ toolChips.length }}</strong>대 표시
        </span>
      </p>
    </section>

    <!-- ===== Service navigation + detail — full width ===== -->
    <div class="flex min-w-0 flex-col gap-3">
      <!-- Service tabs — the tool itself is chosen in the strip above. -->
      <section class="dashboard-surface flex flex-wrap items-center rounded-[var(--sk-r-card)] px-4 py-3">
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
            <span class="px-0.5 sk-label">
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

      <!-- Service detail — gated on the model (DESIGN.md §Layout, scope-bar
           rule): until one is picked there is no tool, and the results name
           the missing choice instead of showing a tool nobody chose. -->
      <AppEmptyState
        v-if="!modelPicked"
        title="모델을 선택하세요."
        description="위 장비 선택에서 모델을 고르면 그 모델의 장비 목록이 열리고, 첫 장비의 H/W 상태가 여기에 표시됩니다. 모델은 여러 개를 함께 고를 수 있습니다."
        hint="장비를 바꾸려면 chip 을 누르세요. 검색과 On/Off 는 고른 모델 안에서 목록을 좁힙니다."
      />
      <AppEmptyState
        v-else-if="!selectedTool"
        title="조건에 맞는 장비가 없습니다."
        :description="`${modelFilters.join(' + ')} 장비 중 검색어와 On/Off 조건을 만족하는 장비가 없습니다.`"
        hint="검색어를 지우거나 On/Off 를 All 로 돌리면 장비가 다시 나타납니다."
      />
      <section
        v-else
        class="dashboard-surface flex-1 rounded-[var(--sk-r-card)] p-4"
      >
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
                name="i-lucide-loader-circle"
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
                    <dt class="sk-field-label">
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

              <!-- BM/PM: master-detail — 예정/이력 job list beside the selected job in full -->
              <EbeamHardwareBmPmPanel
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

              <!-- SCE: 비교 (settings + coefficient curve) / 시계열 (bidaily archive) sub-tabs -->
              <EbeamHardwareScePanel
                v-else-if="activeService === 'sce'"
                :settings="servicePayload.settings ?? {}"
                :docs="servicePayload.docs ?? []"
                :selected-eqp="selectedTool?.eqp_id ?? ''"
                :maintenance-events="overlayEvents"
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
                          class="whitespace-nowrap px-3 py-2 sk-label"
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
</template>
