<template>
  <UModal
    v-model:open="open"
    :ui="{ content: 'w-[88vw] sm:max-w-[760px]' }"
  >
    <!-- The ✕ is hand-rolled because UModal renders its own inside the #header
         slot's FALLBACK — overriding #header drops it. Same classes as the
         stock one (theme `close`), so it lands in the same spot. -->
    <template #header>
      <div class="px-1 py-1 pe-8">
        <p class="sk-eyebrow text-(--sk-brand)">
          WAFER_ALIGN_INFO
        </p>
        <p class="mt-1 sk-heading">
          웨이퍼 정렬 포인트
        </p>
        <p class="mt-1 sk-meta">
          레시피의 wafer alignment 측정점 {{ rows.length }}개. 일반적으로 조회 빈도가 낮아 별도 창으로 분리했습니다.
        </p>
      </div>
      <UButton
        icon="i-lucide-x"
        color="neutral"
        variant="ghost"
        aria-label="닫기"
        class="absolute end-4 top-4"
        @click="open = false"
      />
    </template>

    <template #body>
      <div class="mb-4">
        <div class="mb-1.5 flex items-baseline justify-between gap-2">
          <p class="sk-eyebrow">
            Align Image
          </p>
          <span
            v-if="pending"
            class="sk-meta"
          >불러오는 중…</span>
          <span
            v-else-if="error"
            class="text-xs text-rose-600 dark:text-rose-400"
          >정렬 정보를 불러오지 못했습니다.</span>
        </div>

        <div
          v-if="points.length"
          class="grid grid-cols-2 gap-3"
        >
          <button
            v-for="point in points"
            :key="point.P_No"
            type="button"
            class="group flex min-w-0 flex-col gap-1 text-left"
            :aria-label="`P.No ${point.P_No} 정렬 이미지 확대해서 보기`"
            @click="zoom = point"
          >
            <div class="relative mx-auto aspect-square w-full max-w-[220px] cursor-zoom-in overflow-hidden rounded-md border border-zinc-300/70 bg-(--sk-field) transition-colors group-hover:border-(--sk-brand) dark:border-zinc-700">
              <img
                v-if="point.image"
                :src="imageSrc(point.image)"
                :alt="`P.No ${point.P_No} 정렬 이미지`"
                loading="lazy"
                decoding="async"
                class="h-full w-full object-cover"
              >
              <span class="absolute top-1 left-1 rounded-sm bg-(--sk-ink) px-1.5 py-px font-mono text-xs font-bold tracking-wider text-(--sk-ink-fg)">
                P.No {{ point.P_No }}
              </span>
              <span class="absolute right-1.5 bottom-1 font-mono text-xs text-white/55">⤢</span>
            </div>
            <div class="truncate font-mono text-xs text-(--sk-ink-muted)">
              {{ point.image ?? '—' }}
            </div>
          </button>
        </div>
        <p
          v-else-if="!pending"
          class="sk-meta"
        >
          정렬 이미지가 없습니다.
        </p>
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
    :open="zoom !== null"
    :ui="{ content: 'w-[92vw] sm:max-w-[1020px]', body: 'p-0' }"
    @update:open="value => { if (!value) zoom = null }"
  >
    <template #content>
      <div
        v-if="zoom"
        class="grid h-full max-h-[88vh] grid-cols-1 gap-4 p-4 md:grid-cols-[1.4fr_320px]"
      >
        <div class="relative mx-auto flex aspect-square w-full max-w-[min(100%,78vh)] items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-(--sk-field)">
          <img
            v-if="zoom.image"
            :src="imageSrc(zoom.image)"
            :alt="`P.No ${zoom.P_No} 정렬 이미지`"
            decoding="async"
            class="h-full w-full object-contain"
          >
          <div class="absolute top-3.5 left-3.5 flex items-center gap-2">
            <span class="rounded bg-(--sk-ink) px-2 py-0.5 font-mono text-xs font-bold tracking-wider text-(--sk-ink-fg)">
              P.No {{ zoom.P_No }}
            </span>
            <span class="font-mono text-xs text-white/60">{{ zoom.image }}</span>
          </div>
          <!-- Over the image, not the dialog corner: the corner is occupied by
               the 빔 조건 panel heading. -->
          <button
            type="button"
            class="absolute top-3 right-3 rounded-(--sk-r-nav) bg-black/50 p-1.5 text-white transition-colors duration-200 hover:bg-black/70"
            aria-label="닫기"
            @click="zoom = null"
          >
            <UIcon
              name="i-lucide-x"
              class="h-4 w-4"
            />
          </button>
        </div>

        <div class="max-h-[88vh] space-y-3 overflow-auto">
          <EbeamRecipeOpenSettingTable
            title="빔 조건"
            :block="zoom.cond"
          />
          <EbeamRecipeOpenSettingTable
            title="정렬 조건 (AF / PR)"
            :block="zoom.setting"
          />
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
/**
 * Wafer-align points, with each point's image, beam condition and AF/PR
 * setting fetched from the raw-recipe folder when the popup opens.
 *
 * Fetched on open rather than with the recipe: alignment is looked at rarely,
 * and the fetch costs two files per align point off the tool's FTP server.
 */
import type { TableColumn } from '@nuxt/ui'
import type { IdpLocator, WaferAlignInfoRow } from '~/composables/useRecipeSearchApi'
import { fetchAlignDetail, recipeApiBase, recipeImageUrl } from '~/composables/useRecipeParamDetail'
import type { AlignPoint } from '~/composables/useRecipeParamDetail'
import { formatFixed, recipeTableUi } from '~/utils/recipeView'

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
  toolSlug: string
  locator: IdpLocator
}>()

const zoom = ref<AlignPoint | null>(null)
const points = ref<AlignPoint[]>([])
const pending = ref(false)
const error = ref(false)

// What `points` currently holds data FOR. A plain `points.length` check would
// re-hit the tool on every open when a recipe legitimately has zero align
// points or the last fetch errored, and would never notice the locator
// changing underneath it.
const loadedFor = ref('')
const wantKey = computed(() =>
  `${props.locator.eqp_ip}|${props.locator.idp}|${pNumbers.value.join(',')}`
)

/** Sorted unique P.No — the align table repeats a P.No across rows, and each
 *  distinct one names exactly one file set. */
const pNumbers = computed(() =>
  [...new Set(props.rows.map(row => row['P.No']))].sort((a, b) => a - b)
)

const base = recipeApiBase()

const imageSrc = (name: string) =>
  recipeImageUrl(base, props.toolSlug, props.locator, name)

async function load() {
  const key = wantKey.value
  pending.value = true
  error.value = false
  try {
    points.value = await fetchAlignDetail(props.toolSlug, props.locator, pNumbers.value)
    loadedFor.value = key
  } catch {
    error.value = true
    points.value = []
  } finally {
    pending.value = false
  }
}

watch(open, (isOpen) => {
  if (!isOpen) {
    zoom.value = null
    return
  }
  // The raw folder is immutable for a given recipe, so re-opening the popup on
  // the same locator+points must not re-hit the tool.
  if (loadedFor.value !== wantKey.value && !pending.value) void load()
})

// Formatted through `formatFixed` rather than `.toFixed`: this computed runs
// during render, so anything it throws takes the table AND the modal's close
// button with it — which is exactly what a string `Coordinate.X` from the
// office parser did on 2026-08-05. The backend now coerces to the contract;
// this is the layer that keeps the next violation to a dash.
const displayRows = computed<AlignDisplayRow[]>(() => props.rows.map(row => ({
  Align_No: row.Align_No,
  Chip_X: row['Chip.X'],
  Chip_Y: row['Chip.Y'],
  Coordinate_X: formatFixed(row['Coordinate.X'], 3),
  Coordinate_Y: formatFixed(row['Coordinate.Y'], 3),
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
