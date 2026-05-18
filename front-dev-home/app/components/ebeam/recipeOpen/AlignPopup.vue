<template>
  <UModal
    v-model:open="open"
    :ui="{ content: 'w-[88vw] sm:max-w-[760px]' }"
  >
    <template #header>
      <div class="px-1 py-1">
        <p class="font-mono text-[11px] tracking-wider text-(--sk-brand) uppercase">
          WAFER_ALIGN_INFO
        </p>
        <p class="mt-1 text-[17px] font-bold text-zinc-900 dark:text-zinc-100">
          웨이퍼 정렬 포인트
        </p>
        <p class="mt-1 text-[12px] text-zinc-500">
          레시피의 wafer alignment 측정점 {{ rows.length }}개. 일반적으로 조회 빈도가 낮아 별도 창으로 분리했습니다.
        </p>
      </div>
    </template>

    <template #body>
      <UTable
        class="max-h-[60vh] font-mono-ids"
        :columns="columns"
        :data="displayRows"
        sticky="header"
        :ui="recipeTableUi"
      />
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { WaferAlignInfoRow } from '~/composables/useRecipeSearchApi'
import { recipeTableUi } from '~/utils/recipeView'

type AlignDisplayRow = {
  Align_No: number
  Chip_X: number
  Chip_Y: number
  Coordinate_X: string
  Coordinate_Y: string
  P_No: number
}

const open = defineModel<boolean>('open', { required: true })

const props = defineProps<{
  rows: WaferAlignInfoRow[]
}>()

const displayRows = computed<AlignDisplayRow[]>(() => props.rows.map(row => ({
  Align_No: row.Align_No,
  Chip_X: row['Chip.X'],
  Chip_Y: row['Chip.Y'],
  Coordinate_X: row['Coordinate.X'].toFixed(3),
  Coordinate_Y: row['Coordinate.Y'].toFixed(3),
  P_No: row['P.No']
})))

const columns: TableColumn<AlignDisplayRow>[] = [
  { accessorKey: 'Align_No', header: 'Align_No', size: 86 },
  { accessorKey: 'Chip_X', header: 'Chip.X', size: 80 },
  { accessorKey: 'Chip_Y', header: 'Chip.Y', size: 80 },
  { accessorKey: 'Coordinate_X', header: 'Coordinate.X', size: 118 },
  { accessorKey: 'Coordinate_Y', header: 'Coordinate.Y', size: 118 },
  { accessorKey: 'P_No', header: 'P.No', size: 72 }
]
</script>

<style scoped>
.font-mono-ids :deep(td),
.font-mono-ids :deep(th) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
