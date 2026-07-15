<template>
  <div class="space-y-3">
    <EbeamFeatureHeader
      eyebrow="CD-SEM"
      :title="text.title"
      :subtitle="text.subtitle"
    >
      <template #actions>
        <UButton
          size="md"
          color="neutral"
          variant="subtle"
          icon="i-lucide-arrow-left"
          :label="text.back"
          @click="goBack"
        />
      </template>
    </EbeamFeatureHeader>

    <div
      v-if="selectedLots.length === 0"
      class="dashboard-surface flex flex-col items-center justify-center rounded-2xl px-6 py-16 text-center"
    >
      <div class="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-(--sk-surface) text-(--sk-ink-subtle) ring-1 ring-(--sk-border)">
        <UIcon
          name="i-lucide-inbox"
          class="h-5 w-5"
        />
      </div>
      <p class="text-sm font-medium text-(--sk-ink)">
        {{ text.emptyTitle }}
      </p>
      <p class="mt-1 sk-meta">
        {{ text.emptyDesc }}
      </p>
      <UButton
        class="mt-4"
        size="sm"
        :label="text.emptyCta"
        trailing-icon="i-lucide-arrow-right"
        @click="goBack"
      />
    </div>

    <div
      v-else
      class="dashboard-surface rounded-2xl p-4"
    >
      <p class="mb-3 sk-meta">
        {{ text.legend }}
      </p>

      <div
        v-if="pending"
        class="flex items-center justify-center gap-2 py-16 sk-body"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        {{ text.loading }}
      </div>
      <div
        v-else-if="error"
        class="py-16 text-center sk-body text-rose-600 dark:text-rose-300"
      >
        {{ text.loadError }}
      </div>
      <table
        v-else
        class="w-full border-collapse"
      >
        <thead>
          <tr class="border-b border-(--sk-border)">
            <th class="px-3 py-2 text-left sk-eyebrow">
              디바이스
            </th>
            <th
              v-for="col in COLS"
              :key="col.key"
              class="px-2 py-2 text-right sk-eyebrow"
            >
              {{ col.label }}
            </th>
            <th class="px-2 py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="dev in deviceRows"
            :key="dev.lot_cd"
            class="border-t border-(--sk-border) transition-colors hover:bg-(--sk-accent-tint)/40"
          >
            <td class="px-3 py-1.5 sk-value-num">
              {{ dev.lot_cd }}
            </td>
            <td class="px-2 py-1.5 text-right sk-value-num">
              {{ dev.recipe_count }}
            </td>
            <td class="px-2 py-1.5 text-right sk-value-num">
              {{ dev.param_count }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono text-[12.5px] tabular-nums text-(--sk-ink-muted)">
              {{ dev.median }}
            </td>
            <td class="px-2 py-1.5 text-right">
              <span
                class="inline-flex h-5 min-w-7 items-center justify-center rounded px-1.5 font-mono text-[11px] font-semibold tabular-nums"
                :class="dev.outlier_count > 0
                  ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
                  : 'bg-(--sk-surface) text-(--sk-ink-subtle)'"
              >{{ dev.outlier_count }}</span>
            </td>
            <td class="px-2 py-1.5 text-right">
              <UButton
                size="xs"
                color="neutral"
                variant="outline"
                :label="text.details"
                @click="openDrill(dev.lot_cd)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <EbeamDevstatDrillSlideover
      v-model:open="drillOpen"
      :device="activeDrill"
      highlight-label="초과"
    />
  </div>
</template>

<script setup lang="ts">
import type { RecipeInput } from '~/utils/ruleEngine'
import { detectDeviceOutliers } from '~/utils/outlierDetect'
import { toOutlierDrill, type DrillDevice } from '~/utils/deviceDrill'

definePageMeta({ hideFabSidebar: true })

const { setToolType } = useNavigation()
const { fetchRecipeParams } = useDeviceStatisticsApi()
const { selectedDeviceLots } = useDeviceCart()

const selectedLots = computed(() => selectedDeviceLots.value)

const COLS = [
  { key: 'recipes', label: 'recipe' },
  { key: 'params', label: '파라미터' },
  { key: 'median', label: '중앙값' },
  { key: 'outliers', label: 'outlier' }
] as const

const text = {
  title: '측정 프로파일',
  subtitle: '선택한 디바이스의 측정 point 분포를 비교해 과다 측정 디바이스를 확인합니다.',
  back: '뒤로',
  legend: '행 = 디바이스 · outlier = device 내 point 수가 중앙값×2 를 넘는 파라미터 개수. "자세히"로 recipe·파라미터까지 펼칩니다.',
  details: '자세히',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.',
  emptyTitle: '선택된 디바이스가 없습니다',
  emptyDesc: '디바이스 통계에서 디바이스를 선택해 주세요.',
  emptyCta: '디바이스 선택으로'
} as const

const { data, pending, error } = await useAsyncData<RecipeInput[]>(
  'device-profile',
  () => selectedLots.value.length ? fetchRecipeParams(selectedLots.value) : Promise.resolve([]),
  { watch: [selectedLots] }
)

// Group flat recipe rows by device (lot_cd), preserving cart order.
const recipesByLot = computed(() => {
  const map = new Map<string, RecipeInput[]>()
  for (const r of data.value ?? []) {
    const bucket = map.get(r.lot_cd)
    if (bucket) bucket.push(r)
    else map.set(r.lot_cd, [r])
  }
  return map
})

interface DeviceRow {
  lot_cd: string
  recipe_count: number
  param_count: number
  median: number
  outlier_count: number
}

const deviceRows = computed<DeviceRow[]>(() => {
  const rows: DeviceRow[] = []
  for (const lot_cd of selectedLots.value) {
    const recipes = recipesByLot.value.get(lot_cd) ?? []
    const o = detectDeviceOutliers(recipes)
    rows.push({
      lot_cd,
      recipe_count: recipes.length,
      param_count: recipes.reduce((sum, r) => sum + r.parameters.length, 0),
      median: o.median,
      outlier_count: o.outlier_count
    })
  }
  // Worst (most outliers) first so over-measuring devices surface at the top.
  return rows.sort((a, b) => b.outlier_count - a.outlier_count)
})

const drillOpen = ref(false)
const activeDrill = ref<DrillDevice | null>(null)

const openDrill = (lot_cd: string) => {
  const recipes = recipesByLot.value.get(lot_cd) ?? []
  const ctn = recipes[0]?.ctn_desc ?? ''
  activeDrill.value = toOutlierDrill(lot_cd, ctn, recipes, detectDeviceOutliers(recipes))
  drillOpen.value = true
}

const goBack = async () => {
  await navigateTo('/ebeam/cd-sem/device-statistics')
}

onMounted(() => setToolType('cd-sem'))
</script>
