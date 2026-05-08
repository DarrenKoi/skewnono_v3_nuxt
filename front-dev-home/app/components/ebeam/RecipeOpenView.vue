<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Fab } from '~/stores/navigation'
import type {
  IdpImageInfoRow,
  RecipeDetailResponse,
  RecipeSearchToolType,
  WaferMpInfoRow
} from '~/composables/useRecipeSearchApi'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: RecipeSearchToolType
}>()

type WaferAlignDisplayRow = {
  Align_No: number
  Chip_X: number
  Chip_Y: number
  Coordinate_X: number
  Coordinate_Y: number
  P_No: number
}

const route = useRoute()
const { fetchRecipeDetail } = useRecipeSearchApi()

const recipeName = computed(() => {
  const raw = route.query.recipe_name
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value.trim() : ''
})

const backRoute = computed(() => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`)
const cacheKey = computed(() => `recipe-open:${props.toolType}:${props.fab || 'ALL'}:${recipeName.value}`)

const { data, pending, error, refresh } = await useAsyncData<RecipeDetailResponse | null>(
  () => cacheKey.value,
  () => {
    if (!recipeName.value) {
      return Promise.resolve(null)
    }

    return fetchRecipeDetail({
      toolType: props.toolType,
      fabName: props.fab,
      recipeName: recipeName.value
    })
  },
  {
    watch: [cacheKey],
    default: () => null,
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const waferMpRows = computed(() => data.value?.wafer_mp_info ?? [])
const waferAlignRows = computed<WaferAlignDisplayRow[]>(() => {
  return (data.value?.wafer_align_info ?? []).map(row => ({
    Align_No: row.Align_No,
    Chip_X: row['Chip.X'],
    Chip_Y: row['Chip.Y'],
    Coordinate_X: row['Coordinate.X'],
    Coordinate_Y: row['Coordinate.Y'],
    P_No: row['P.No']
  }))
})
const idpImageRows = computed(() => data.value?.idp_image_info ?? [])

const titleRecipeName = computed(() => data.value?.recipe_id ?? recipeName.value)

const formatTimestamp = (iso: string) => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso

  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`
}

const statCells = computed(() => [
  { label: '측정 포인트', value: waferMpRows.value.length },
  { label: 'Align 포인트', value: waferAlignRows.value.length },
  { label: 'Image 정의', value: idpImageRows.value.length }
])

const waferMpColumns: TableColumn<WaferMpInfoRow>[] = [
  { accessorKey: 'ChipNo_X', header: 'ChipNo_X', size: 86 },
  { accessorKey: 'ChipNo_Y', header: 'ChipNo_Y', size: 86 },
  { accessorKey: 'Coordinate_X', header: 'Coordinate_X', size: 118 },
  { accessorKey: 'Coordinate_Y', header: 'Coordinate_Y', size: 118 },
  { accessorKey: 'P_No', header: 'P_No', size: 70 },
  { accessorKey: 'D_No', header: 'D_No', size: 70 },
  { accessorKey: 'Diff', header: 'Diff', size: 76 },
  { accessorKey: 'Rel', header: 'Rel', size: 70 },
  { accessorKey: 'Rel_MoveX', header: 'Rel_MoveX', size: 104 },
  { accessorKey: 'RelMoveY', header: 'RelMoveY', size: 104 },
  { accessorKey: 'Coordinate_X_r', header: 'Coordinate_X_r', size: 128 },
  { accessorKey: 'Coordinate_Y_r', header: 'Coordinate_Y_r', size: 128 },
  { accessorKey: 'Parameter', header: 'Parameter', size: 96 },
  { accessorKey: 'img_meas2', header: 'img_meas2', size: 138 }
]

const waferAlignColumns: TableColumn<WaferAlignDisplayRow>[] = [
  { accessorKey: 'Align_No', header: 'Align_No', size: 86 },
  { accessorKey: 'Chip_X', header: 'Chip.X', size: 80 },
  { accessorKey: 'Chip_Y', header: 'Chip.Y', size: 80 },
  { accessorKey: 'Coordinate_X', header: 'Coordinate.X', size: 118 },
  { accessorKey: 'Coordinate_Y', header: 'Coordinate.Y', size: 118 },
  { accessorKey: 'P_No', header: 'P.No', size: 72 }
]

const idpImageColumns: TableColumn<IdpImageInfoRow>[] = [
  { accessorKey: 'Parameter', header: 'Parameter', size: 96 },
  { accessorKey: 'img_add1', header: 'img_add1', size: 134 },
  { accessorKey: 'img_add2', header: 'img_add2', size: 134 },
  { accessorKey: 'img_meas1', header: 'img_meas1', size: 138 },
  { accessorKey: 'img_meas2', header: 'img_meas2', size: 138 },
  { accessorKey: 'SEQ', header: 'SEQ', size: 64 },
  { accessorKey: 'Last_SEQ', header: 'Last_SEQ', size: 88 },
  { accessorKey: 'Region', header: 'Region', size: 78 },
  { accessorKey: 'image_add3', header: 'image_add3', size: 138 },
  { accessorKey: 'Addressing', header: 'Addressing', size: 104 },
  { accessorKey: 'Mother_Para', header: 'Mother_Para', size: 112 },
  { accessorKey: 'Double_Addressing', header: 'Double_Addressing', size: 146 },
  { accessorKey: 'Meas_Counting', header: 'Meas_Counting', size: 122 },
  { accessorKey: 'dnumber_removed', header: 'dnumber_removed', size: 132 }
]

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis',
  th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div class="min-w-0">
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-arrow-left"
          label="목록으로"
          :to="backRoute"
        />
        <p class="mt-3 text-sm font-medium text-zinc-500 dark:text-zinc-400">
          {{ toolLabel }} · {{ fab }}
        </p>
        <h1 class="mt-1 break-all text-2xl font-bold text-zinc-950 dark:text-zinc-50">
          {{ titleRecipeName || 'Recipe 상세' }}
        </h1>
        <p
          v-if="data"
          class="mt-1 text-xs text-zinc-500 dark:text-zinc-400"
        >
          {{ data.fac_id }} · {{ data.tool_category }} · {{ formatTimestamp(data.timestamp) }}
        </p>
      </div>

      <div
        v-if="data"
        class="dashboard-surface flex overflow-hidden rounded-2xl self-start md:self-auto"
      >
        <div
          v-for="(cell, index) in statCells"
          :key="cell.label"
          class="flex min-w-[108px] flex-col gap-0.5 px-5 py-2.5"
          :class="{ 'border-l border-zinc-200/70 dark:border-zinc-800/70': index > 0 }"
        >
          <span class="text-[22px] font-bold leading-none tabular-nums text-zinc-900 dark:text-zinc-100">
            {{ cell.value.toLocaleString() }}
          </span>
          <span class="text-[11px] text-zinc-500">{{ cell.label }}</span>
        </div>
      </div>
    </div>

    <div
      v-if="!recipeName"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="mx-auto h-6 w-6 text-rose-500"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        Recipe 이름이 없습니다.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        label="Recipe 검색으로 돌아가기"
        :to="backRoute"
      />
    </div>

    <div
      v-else-if="pending"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-zinc-500"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mx-auto h-5 w-5 animate-spin text-zinc-400"
      />
      <p class="mt-2">
        Recipe 내용을 불러오는 중입니다.
      </p>
    </div>

    <div
      v-else-if="error"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="mx-auto h-6 w-6 text-rose-500"
      />
      <p class="mt-2 text-sm font-medium text-rose-600 dark:text-rose-300">
        Recipe 내용을 불러오지 못했습니다.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-refresh-cw"
        label="Retry"
        @click="refresh()"
      />
    </div>

    <template v-else-if="data">
      <section class="dashboard-surface rounded-2xl px-3.5 py-3">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            wafer_mp_info
          </h2>
          <span class="font-mono text-[11px] tabular-nums text-zinc-500">
            {{ waferMpRows.length.toLocaleString() }} rows
          </span>
        </div>
        <UTable
          class="max-h-[24rem] font-mono-ids"
          :columns="waferMpColumns"
          :data="waferMpRows"
          sticky="header"
          :ui="tableUi"
        >
          <template #Diff-cell="{ row }">
            <UBadge
              :label="row.original.Diff ? 'True' : 'False'"
              :color="row.original.Diff ? 'success' : 'neutral'"
              size="xs"
              variant="subtle"
            />
          </template>
          <template #Rel-cell="{ row }">
            <UBadge
              :label="row.original.Rel ? 'True' : 'False'"
              :color="row.original.Rel ? 'success' : 'neutral'"
              size="xs"
              variant="subtle"
            />
          </template>
        </UTable>
      </section>

      <section class="dashboard-surface rounded-2xl px-3.5 py-3">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            wafer_align_info
          </h2>
          <span class="font-mono text-[11px] tabular-nums text-zinc-500">
            {{ waferAlignRows.length.toLocaleString() }} rows
          </span>
        </div>
        <UTable
          class="max-h-[18rem] font-mono-ids"
          :columns="waferAlignColumns"
          :data="waferAlignRows"
          sticky="header"
          :ui="tableUi"
        />
      </section>

      <section class="dashboard-surface rounded-2xl px-3.5 py-3">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            idp_image_info
          </h2>
          <span class="font-mono text-[11px] tabular-nums text-zinc-500">
            {{ idpImageRows.length.toLocaleString() }} rows
          </span>
        </div>
        <UTable
          class="max-h-[22rem] font-mono-ids"
          :columns="idpImageColumns"
          :data="idpImageRows"
          sticky="header"
          :ui="tableUi"
        >
          <template #Double_Addressing-cell="{ row }">
            <UBadge
              :label="row.original.Double_Addressing ? 'True' : 'False'"
              :color="row.original.Double_Addressing ? 'success' : 'neutral'"
              size="xs"
              variant="subtle"
            />
          </template>
        </UTable>
      </section>
    </template>
  </div>
</template>

<style scoped>
.font-mono-ids :deep(td),
.font-mono-ids :deep(th) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
