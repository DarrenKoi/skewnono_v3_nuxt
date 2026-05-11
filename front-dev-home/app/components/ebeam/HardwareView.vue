<script setup lang="ts">
import type { Fab, ToolType } from '~/stores/navigation'
import type { SemListRow } from '~/composables/useSemListApi'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: ToolType
}>()

type HardwareServiceKey = 'bsm' | 'fdc' | 'bm-pm'

type HardwareService = {
  key: HardwareServiceKey
  label: string
  title: string
  description: string
  icon: string
}

const hardwareServices: HardwareService[] = [
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
  },
  {
    key: 'bm-pm',
    label: 'BM/PM',
    title: 'BM / PM Information',
    description: '장비별 BM 이력, PM 일정, maintenance window를 함께 확인합니다.',
    icon: 'i-lucide-wrench'
  }
]
const defaultHardwareService = hardwareServices[0]!

const { filterRows } = useSemListApi()
const { data: allRows } = await useSemList()

const activeService = ref<HardwareServiceKey>('bsm')
const modelFilter = ref('all')
const toolSearch = ref('')
const selectedToolId = ref('')

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

const availabilityTone = computed(() => selectedTool.value?.available === 'On' ? 'ok' : 'bad')

const summaryStats = computed(() => [
  { label: 'Tools', value: rows.value.length, tone: 'neutral' },
  { label: 'Matched', value: searchedRows.value.length, tone: 'accent' },
  { label: 'Status', value: selectedTool.value?.available ?? '-', tone: availabilityTone.value }
])

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
</script>

<template>
  <div class="space-y-3">
    <EbeamFeatureHeader
      :title="`${toolLabel} H/W 관리 - ${fab}`"
      subtitle="BSM, FDC, BM/PM 정보를 선택한 장비 기준으로 확인합니다."
      :stats="summaryStats"
      stat-size="sm"
    />

    <div class="flex flex-wrap gap-2">
      <SkNavPill
        v-for="service in hardwareServices"
        :key="service.key"
        :label="service.label"
        :icon="service.icon"
        :active="activeService === service.key"
        size="md"
        @click="activeService = service.key"
      />
    </div>

    <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section class="dashboard-surface rounded-2xl p-4">
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
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

          <div
            class="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold"
            :class="selectedTool?.available === 'On'
              ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:ring-emerald-800'
              : 'bg-rose-50 text-rose-700 ring-1 ring-rose-200 dark:bg-rose-950/40 dark:text-rose-200 dark:ring-rose-800'"
          >
            <span class="h-2 w-2 rounded-full bg-current" />
            {{ selectedTool?.available ?? 'No tool' }}
          </div>
        </div>

        <div class="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <div class="rounded-xl border border-zinc-200/70 p-3 dark:border-zinc-800/70">
            <p class="text-[11px] font-medium text-zinc-500">
              Equipment ID
            </p>
            <p class="mt-1 truncate font-mono text-sm font-bold text-zinc-950 dark:text-zinc-50">
              {{ selectedTool?.eqp_id ?? '-' }}
            </p>
          </div>
          <div class="rounded-xl border border-zinc-200/70 p-3 dark:border-zinc-800/70">
            <p class="text-[11px] font-medium text-zinc-500">
              Model
            </p>
            <p class="mt-1 truncate text-sm font-semibold text-zinc-950 dark:text-zinc-50">
              {{ selectedTool?.eqp_model_cd ?? '-' }}
            </p>
          </div>
          <div class="rounded-xl border border-zinc-200/70 p-3 dark:border-zinc-800/70">
            <p class="text-[11px] font-medium text-zinc-500">
              IP Address
            </p>
            <p class="mt-1 truncate font-mono text-sm font-semibold text-zinc-950 dark:text-zinc-50">
              {{ selectedTool?.eqp_ip ?? '-' }}
            </p>
          </div>
          <div class="rounded-xl border border-zinc-200/70 p-3 dark:border-zinc-800/70">
            <p class="text-[11px] font-medium text-zinc-500">
              Version
            </p>
            <p class="mt-1 text-sm font-semibold text-zinc-950 dark:text-zinc-50">
              {{ selectedTool?.version ?? '-' }}
            </p>
          </div>
        </div>

        <div class="mt-4 rounded-xl bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:bg-zinc-900/60 dark:text-zinc-300">
          <span class="font-semibold text-zinc-900 dark:text-zinc-100">{{ activeServiceDetail.label }}</span>
          정보는 선택한 장비를 기준으로 열립니다. API가 연결되면 이 영역에 trend, 이력, 상세 판정 결과를 표시합니다.
        </div>
      </section>

      <aside class="dashboard-surface rounded-2xl p-4">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-list-filter"
            class="h-4 w-4 text-(--sk-accent)"
          />
          <h2 class="text-sm font-bold text-zinc-950 dark:text-zinc-50">
            Tool Selection
          </h2>
        </div>

        <div class="mt-4 space-y-3">
          <UInput
            v-model="toolSearch"
            icon="i-lucide-search"
            color="neutral"
            variant="subtle"
            placeholder="Equipment ID, Model, IP 검색"
          />

          <USelect
            v-model="modelFilter"
            color="neutral"
            variant="subtle"
            :items="modelOptions"
          />

          <USelect
            v-model="selectedToolId"
            color="neutral"
            variant="subtle"
            :items="toolOptions"
            :disabled="toolOptions.length === 0"
            placeholder="Tool 선택"
          />
        </div>

        <div class="mt-4 rounded-xl border border-zinc-200/70 p-3 dark:border-zinc-800/70">
          <p class="text-[11px] font-medium text-zinc-500">
            Search Result
          </p>
          <p class="mt-1 text-sm font-semibold text-zinc-950 dark:text-zinc-50">
            {{ searchedRows.length }} / {{ rows.length }} tools
          </p>
          <p class="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            dropdown은 현재 검색어와 model filter를 반영합니다.
          </p>
        </div>
      </aside>
    </div>
  </div>
</template>
