<script setup lang="ts">
import type { Fab, ToolType } from '~/stores/navigation'
import type { SemListRow } from '~/composables/useSemListApi'
import type { HardwarePayload, HardwareServiceKey } from '~/composables/useHardwareApi'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: ToolType
}>()

type HardwareService = {
  key: HardwareServiceKey
  label: string
  title: string
  description: string
  icon: string
}

// BM/PM leads the pill row and seeds the default tab because maintenance
// data exists for every tool; BSM/FDC availability varies per equipment.
const hardwareServices: HardwareService[] = [
  {
    key: 'bm-pm',
    label: 'BM/PM',
    title: 'BM / PM Information',
    description: '장비별 BM 이력, PM 일정, maintenance window를 함께 확인합니다.',
    icon: 'i-lucide-wrench'
  },
  {
    key: 'bsm',
    label: 'BSM',
    title: 'Beam Shape Matching',
    description: 'Beam profile, shape drift, matching result를 선택한 장비 기준으로 확인합니다.',
    icon: 'i-lucide-radar'
  },
  {
    key: 'fdc',
    label: 'FDC',
    title: 'Fault Detection & Classification',
    description: '실시간 fault signal, alarm trend, classification 상태를 장비 단위로 확인합니다.',
    icon: 'i-lucide-activity'
  }
]
const defaultHardwareService = hardwareServices[0]!

const { filterRows } = useSemListApi()
const { data: allRows } = await useSemList()
const { selectedToolId: storeSelectedToolId, setSelectedTool } = useNavigation()
const { fetchService } = useHardwareApi()

const activeService = ref<HardwareServiceKey>(defaultHardwareService.key)
const modelFilter = ref('all')
const toolSearch = ref('')
const selectedToolId = ref(storeSelectedToolId.value)

// Clear after consume so the store doesn't override later in-page picks on this visit.
if (storeSelectedToolId.value) {
  setSelectedTool('')
}

const rows = computed<SemListRow[]>(() => filterRows(allRows.value ?? [], props.toolType, props.fab))

const modelOptions = computed(() => [
  { label: 'All Models', value: 'all' },
  ...Array.from(new Set(rows.value.map(row => row.eqp_model_cd)))
    .sort((left, right) => left.localeCompare(right))
    .map(model => ({ label: model, value: model }))
])

const searchedRows = computed(() => {
  const query = toolSearch.value.trim().toLowerCase()

  return rows.value.filter((row) => {
    const matchesModel = modelFilter.value === 'all' || row.eqp_model_cd === modelFilter.value
    const matchesSearch = query.length === 0 || [
      row.eqp_id,
      row.eqp_model_cd,
      row.eqp_ip,
      row.vendor_nm,
      row.available
    ].some(value => value.toLowerCase().includes(query))

    return matchesModel && matchesSearch
  })
})

const toolOptions = computed(() =>
  searchedRows.value.map(row => ({
    label: `${row.eqp_id} · ${row.eqp_model_cd}`,
    value: row.eqp_id
  }))
)

const selectedTool = computed(() => {
  return rows.value.find(row => row.eqp_id === selectedToolId.value) ?? searchedRows.value[0] ?? rows.value[0] ?? null
})

const activeServiceDetail = computed<HardwareService>(() => {
  return hardwareServices.find(service => service.key === activeService.value) ?? defaultHardwareService
})

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
    fabId: selectedTool.value?.fab_name
  }),
  {
    watch: [() => props.toolType, () => props.fab, activeService, () => selectedTool.value?.eqp_id]
  }
)

const serviceDetailEntries = computed(() => {
  const details = servicePayload.value?.details
  if (!details) return []
  return Object.entries(details)
})
</script>

<template>
  <div class="space-y-3">
    <EbeamFeatureHeader
      :title="`${toolLabel} H/W 관리 - ${fab}`"
      subtitle="BSM, FDC, BM/PM 정보를 선택한 장비 기준으로 확인합니다."
    />

    <section class="dashboard-surface mx-auto w-full max-w-3xl rounded-2xl p-4">
      <div class="flex flex-col gap-2 md:flex-row md:items-center">
        <USelect
          v-model="modelFilter"
          color="neutral"
          variant="subtle"
          :items="modelOptions"
          class="md:w-28"
        />
        <USelect
          v-model="selectedToolId"
          color="neutral"
          variant="subtle"
          :items="toolOptions"
          :disabled="toolOptions.length === 0"
          placeholder="Tool 선택"
          class="md:w-48"
        />
        <UInput
          v-model="toolSearch"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="Equipment ID, Model, IP 검색"
          class="md:w-56"
        />
        <span class="font-mono tabular-nums text-xs text-zinc-500 dark:text-zinc-400 md:ml-auto">
          {{ searchedRows.length }} / {{ rows.length }} tools
        </span>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-zinc-200/70 pt-3 text-xs text-zinc-500 dark:border-zinc-800/70 dark:text-zinc-400">
        <template v-if="selectedTool">
          <span class="font-mono text-sm font-bold text-zinc-950 dark:text-zinc-50">
            {{ selectedTool.eqp_id }}
          </span>
          <span class="text-zinc-300 dark:text-zinc-700">·</span>
          <span class="font-medium text-zinc-700 dark:text-zinc-200">
            {{ selectedTool.vendor_nm }} {{ selectedTool.eqp_model_cd }}
          </span>
          <span class="text-zinc-300 dark:text-zinc-700">·</span>
          <span
            class="inline-flex items-center gap-1.5 font-semibold"
            :class="selectedTool.available === 'On'
              ? 'text-emerald-700 dark:text-emerald-300'
              : 'text-rose-700 dark:text-rose-300'"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-current" />
            {{ selectedTool.available }}
          </span>
          <span class="text-zinc-300 dark:text-zinc-700">·</span>
          <span>{{ selectedTool.fab_name }}</span>
          <span class="text-zinc-300 dark:text-zinc-700">·</span>
          <span class="font-mono">{{ selectedTool.eqp_ip }}</span>
          <span class="text-zinc-300 dark:text-zinc-700">·</span>
          <span>v{{ selectedTool.version }}</span>
        </template>
        <span v-else>—</span>
        <div class="ml-auto inline-flex gap-1">
          <SkNavPill
            v-for="service in hardwareServices"
            :key="service.key"
            :label="service.label"
            :icon="service.icon"
            :active="activeService === service.key"
            size="sm"
            @click="activeService = service.key"
          />
        </div>
      </div>
    </section>

    <section class="dashboard-surface rounded-2xl p-4">
      <div class="min-w-0">
        <p class="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500 dark:text-zinc-400">
          {{ activeServiceDetail.label }}
        </p>
        <h2 class="mt-1 text-lg font-bold text-zinc-950 dark:text-zinc-50">
          {{ activeServiceDetail.title }}
        </h2>
        <p class="mt-1 max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
          {{ activeServiceDetail.description }}
        </p>
      </div>

      <div class="mt-4 rounded-xl bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:bg-zinc-900/60 dark:text-zinc-300">
        <template v-if="servicePending">
          <span class="inline-flex items-center gap-2">
            <UIcon name="i-lucide-loader-2" class="h-4 w-4 animate-spin" />
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
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span class="font-semibold text-zinc-900 dark:text-zinc-100">{{ activeServiceDetail.label }}</span>
              <span
                class="inline-flex items-center gap-1.5 text-xs font-semibold"
                :class="servicePayload.available
                  ? 'text-emerald-700 dark:text-emerald-300'
                  : 'text-amber-700 dark:text-amber-300'"
              >
                <span class="h-1.5 w-1.5 rounded-full bg-current" />
                {{ servicePayload.available ? 'Available' : 'Not available' }}
              </span>
              <span class="text-xs font-mono text-zinc-400 dark:text-zinc-500">
                {{ servicePayload.fetched_at }}
              </span>
            </div>
            <p>{{ servicePayload.summary }}</p>
            <dl
              v-if="serviceDetailEntries.length"
              class="mt-1 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2"
            >
              <div
                v-for="[key, value] in serviceDetailEntries"
                :key="key"
                class="flex items-baseline gap-2"
              >
                <dt class="font-medium text-zinc-500 dark:text-zinc-400">
                  {{ key }}
                </dt>
                <dd class="font-mono tabular-nums text-zinc-900 dark:text-zinc-100">
                  {{ value }}
                </dd>
              </div>
            </dl>
          </div>
        </template>
        <span v-else>
          <span class="font-semibold text-zinc-900 dark:text-zinc-100">{{ activeServiceDetail.label }}</span>
          정보는 선택한 장비를 기준으로 열립니다.
        </span>
      </div>
    </section>
  </div>
</template>
