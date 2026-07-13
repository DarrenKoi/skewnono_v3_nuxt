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
        <p class="mt-1 text-[12px] text-(--sk-ink-muted)">
          레시피의 wafer alignment 측정점 {{ rows.length }}개. 일반적으로 조회 빈도가 낮아 별도 창으로 분리했습니다.
        </p>
      </div>
    </template>

    <template #body>
      <div
        v-if="images.length"
        class="mb-4"
      >
        <p class="mb-1.5 font-mono text-[10px] font-bold tracking-wider text-(--sk-ink-muted) uppercase">
          Align Image
        </p>
        <div class="grid grid-cols-2 gap-3">
          <button
            v-for="img in images"
            :key="img.filename"
            type="button"
            class="group flex min-w-0 flex-col gap-1 text-left"
            :aria-label="`${img.label} 확대해서 보기`"
            @click="zoomImage = img"
          >
            <div class="relative mx-auto aspect-square w-full max-w-[220px] cursor-zoom-in overflow-hidden rounded-md border border-zinc-300/70 bg-[#23201B] transition-colors group-hover:border-(--sk-brand) dark:border-zinc-700">
              <EbeamRecipeOpenSemNoise />
              <span class="absolute top-1 left-1 rounded-sm bg-(--sk-ink) px-1.5 py-px font-mono text-[9px] font-bold tracking-wider text-(--sk-ink-fg)">
                {{ img.label }}
              </span>
              <span class="absolute right-1.5 bottom-1 font-mono text-[10px] text-white/55">⤢</span>
            </div>
            <div class="truncate font-mono text-[9.5px] text-(--sk-ink-muted)">
              {{ img.filename }}
            </div>
          </button>
        </div>
      </div>

      <UTable
        class="max-h-[60vh] font-mono-ids"
        :columns="columns"
        :data="displayRows"
        sticky="header"
        :ui="recipeTableUi"
      />
    </template>
  </UModal>

  <UModal
    :open="zoomImage !== null"
    :ui="{ content: 'w-[92vw] sm:max-w-[920px]', body: 'p-0' }"
    @update:open="value => { if (!value) zoomImage = null }"
  >
    <template #content>
      <div
        v-if="zoomImage"
        class="relative mx-auto flex aspect-square w-full max-w-[min(100%,82vh)] items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-[#1A1813]"
      >
        <EbeamRecipeOpenSemNoise />
        <div class="relative font-mono text-[80px] font-bold tracking-widest text-white/10">
          ALIGN
        </div>
        <div class="absolute top-3.5 left-3.5 flex items-center gap-2">
          <span class="rounded bg-(--sk-ink) px-2 py-0.5 font-mono text-[10px] font-bold tracking-wider text-(--sk-ink-fg)">
            {{ zoomImage.label }}
          </span>
          <span class="font-mono text-[11px] text-white/60">{{ zoomImage.filename }}</span>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { AlignImage, WaferAlignInfoRow } from '~/composables/useRecipeSearchApi'
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

const props = withDefaults(defineProps<{
  rows: WaferAlignInfoRow[]
  images?: AlignImage[]
}>(), {
  images: () => []
})

const zoomImage = ref<AlignImage | null>(null)

watch(open, (isOpen) => {
  if (!isOpen) zoomImage.value = null
})

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
