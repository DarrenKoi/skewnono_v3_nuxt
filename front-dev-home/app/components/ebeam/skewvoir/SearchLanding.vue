<template>
  <div class="space-y-4">
    <!-- Landing header -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="font-mono text-[11px] tracking-wide text-(--sk-ink-subtle)">
          {{ toolLabel }} · SKEWVOIR
        </p>
        <h1 class="mt-0.5 text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          측정 결과 검색
        </h1>
        <p class="mt-1 text-[12.5px] text-(--sk-ink-muted)">
          Lot · Recipe · 장비로 측정을 찾고, 결과를 열면 분석 워크스페이스로 이동합니다.
        </p>
      </div>

      <!-- Saved views -->
      <UPopover>
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-bookmark"
          :label="`저장된 뷰 ${savedViews.views.value.length}`"
          size="sm"
        />
        <template #content>
          <div class="w-80 p-2">
            <p class="px-2 py-1 font-mono text-[10px] font-semibold tracking-wider text-zinc-400">
              SAVED VIEWS
            </p>
            <p
              v-if="!savedViews.views.value.length"
              class="px-2 py-3 text-[12px] text-(--sk-ink-muted)"
            >
              저장된 뷰가 없습니다. 분석 화면에서 “Save view”로 저장하세요.
            </p>
            <ul
              v-else
              class="max-h-72 space-y-0.5 overflow-y-auto"
            >
              <li
                v-for="v in savedViews.views.value"
                :key="v.id"
                class="group flex items-center gap-2 rounded-(--sk-r-nav) px-2 py-1.5 hover:bg-zinc-500/10"
              >
                <button
                  type="button"
                  class="min-w-0 flex-1 text-left"
                  @click="openSaved(v)"
                >
                  <span class="block truncate text-[12.5px] font-medium text-zinc-800 dark:text-zinc-100">{{ v.name }}</span>
                  <span class="block truncate font-mono text-[10.5px] text-(--sk-ink-subtle)">{{ String(v.query.lot ?? '') }}</span>
                </button>
                <button
                  type="button"
                  class="opacity-0 transition-opacity group-hover:opacity-100"
                  @click="savedViews.remove(v.id)"
                >
                  <UIcon
                    name="i-lucide-x"
                    class="h-3.5 w-3.5 text-zinc-400 hover:text-(--sk-bad)"
                  />
                </button>
              </li>
            </ul>
          </div>
        </template>
      </UPopover>
    </div>

    <!-- Search bar -->
    <div class="dashboard-surface rounded-(--sk-r-card) p-3">
      <p class="mb-2 px-0.5 text-[11px] text-zinc-400">
        검색 · <span class="font-semibold text-zinc-600 dark:text-zinc-300">Lot / Recipe / Machine</span>
        · Elastic Search · 1.2M scans · last 90d
      </p>
      <div class="flex items-center gap-2">
        <UInput
          v-model="queryText"
          class="flex-1"
          icon="i-lucide-search"
          placeholder="MCD018, RK2W011, VMGTET, lot:RK2A052AN, MP:WAFER…"
          size="md"
        />
        <UButton
          class="bg-(--sk-ink) text-(--sk-ink-fg)"
          label="Search"
          icon="i-lucide-corner-down-left"
          size="md"
        />
      </div>

      <!-- Filters -->
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <span class="font-mono text-[10px] tracking-wide text-zinc-400">FILTERS</span>
        <button
          v-for="opt in dropdownFilters"
          :key="opt.label"
          type="button"
          class="inline-flex h-7 items-center gap-1.5 rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-surface) px-2.5 text-[12px] text-zinc-600 hover:bg-zinc-500/5 dark:text-zinc-300"
        >
          <span class="text-zinc-400">{{ opt.label }}:</span>
          <span class="font-medium text-zinc-800 dark:text-zinc-100">{{ opt.value }}</span>
          <UIcon
            name="i-lucide-chevron-down"
            class="h-3 w-3 opacity-50"
          />
        </button>

        <span
          v-for="chip in chipFilters"
          :key="chip"
          class="inline-flex h-7 items-center gap-1.5 rounded-(--sk-r-chip) bg-(--sk-brand) px-2.5 font-mono text-[11.5px] font-medium text-(--sk-brand-fg)"
        >
          {{ chip }}
          <UIcon
            name="i-lucide-x"
            class="h-3 w-3 opacity-70"
          />
        </span>
      </div>
    </div>

    <!-- Result timeline + quick stats (structure placeholders this pass) -->
    <div class="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_22rem]">
      <EbeamSkewvoirPanelFrame
        title="Result Timeline"
        :meta="`${analyzableRows.length} measurements`"
        icon="i-lucide-gantt-chart"
        placeholder-height="min-h-56"
      />
      <EbeamSkewvoirPanelFrame
        title="Quick Stats by Recipe"
        meta="recipe rollup"
        icon="i-lucide-table-2"
        placeholder-height="min-h-56"
      />
    </div>

    <!-- Latest measurements — real mock rows; opening one enters analysis -->
    <section class="dashboard-surface flex flex-col rounded-(--sk-r-card)">
      <header class="flex items-center justify-between gap-2 border-b border-(--sk-border-soft) px-3 py-2">
        <div class="flex items-baseline gap-2">
          <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            Latest Measurements
          </h2>
          <span class="font-mono text-[10.5px] text-(--sk-ink-subtle)">
            {{ visibleRows.length }} of {{ analyzableRows.length }}
          </span>
        </div>
        <span class="font-mono text-[10.5px] text-zinc-400">클릭하여 분석 열기</span>
      </header>

      <div
        v-if="pending"
        class="flex items-center justify-center gap-2 px-4 py-12 text-[12px] text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        측정 이력을 불러오는 중입니다.
      </div>

      <table
        v-else
        class="w-full border-collapse text-[12px]"
      >
        <thead>
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-zinc-400">
            <th class="px-3 py-1.5 font-medium">
              LOT
            </th>
            <th class="px-3 py-1.5 font-medium">
              RECIPE
            </th>
            <th class="px-3 py-1.5 font-medium">
              EQ
            </th>
            <th class="px-3 py-1.5 font-medium">
              FAB
            </th>
            <th class="px-3 py-1.5 font-medium">
              CAPTURED
            </th>
            <th class="px-3 py-1.5" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in visibleRows"
            :key="row.id"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0 hover:bg-(--sk-brand)/5"
            @click="open(row)"
          >
            <td class="px-3 py-2 font-mono font-semibold text-zinc-900 dark:text-zinc-100">
              {{ row.lot_id }}
            </td>
            <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
              {{ row.recipe_name }}
            </td>
            <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
              {{ row.eqp_id }}
            </td>
            <td class="px-3 py-2">
              <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-1.5 py-0.5 font-mono text-[11px] text-(--sk-chip-text)">
                {{ row.fab_name }}
              </span>
            </td>
            <td class="px-3 py-2 font-mono text-(--sk-ink-muted)">
              {{ row.timestamp }}
            </td>
            <td class="px-3 py-2 text-right">
              <UIcon
                name="i-lucide-arrow-right"
                class="h-3.5 w-3.5 text-zinc-300"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { MeasHistResponse, MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { SkewvoirSavedView } from '~/composables/useSkewvoirSavedViews'
import type { SkewvoirSelection } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{
  toolLabel: string
  toolType: MeasHistToolType
}>()

const ws = useSkewvoirWorkspace(props.toolType, props.toolLabel)
const savedViews = useSkewvoirSavedViews(props.toolType)
const { fetchMeasHist } = useMeasHistApi()
const router = useRouter()

const queryText = ref('')

const cacheKey = computed(() => `skewvoir-meas-hist:${props.toolType}`)

const { data, pending } = await useAsyncData<MeasHistResponse>(
  () => cacheKey.value,
  () => fetchMeasHist({ toolType: props.toolType }),
  {
    watch: [cacheKey],
    default: () => ({ tool_type: props.toolType, fab_name: null, recipe_name: null, total: 0, rows: [] }),
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const analyzableRows = computed<MeasHistRow[]>(() =>
  (data.value?.rows ?? []).filter(row => row.msr_check === 'Yes')
)

const visibleRows = computed(() => analyzableRows.value.slice(0, 12))

const toSelection = (row: MeasHistRow): SkewvoirSelection => ({
  lot: row.lot_id,
  recipe: row.recipe_name,
  eq: row.eqp_id,
  mp: 'WAFER',
  capturedAt: row.timestamp
})

const open = (row: MeasHistRow) => ws.openAnalysis(toSelection(row))

const openSaved = (v: SkewvoirSavedView) =>
  router.push({ path: ws.analysisPath, query: v.query })

const f = computed(() => ws.pinnedFilters.value)

const dropdownFilters = computed(() => [
  { label: 'Area', value: 'ALL' },
  { label: 'FAB', value: f.value.fab },
  { label: '장비 종류', value: f.value.eqType },
  { label: 'EQ', value: 'ALL' },
  { label: '기간', value: f.value.period }
])

const chipFilters = computed(() => [`MP : ${f.value.mp}`, ...f.value.flags])
</script>
