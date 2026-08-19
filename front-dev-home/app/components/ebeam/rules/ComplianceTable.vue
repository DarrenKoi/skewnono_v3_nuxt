<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-3">
    <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
      <h3 class="sk-title">
        {{ text.title }}
      </h3>
      <span class="sk-meta">
        {{ text.legend }}
      </span>
    </div>

    <div
      v-if="r3Lots.length === 0"
      class="px-4 py-12 text-center sk-body"
    >
      {{ text.empty }}
    </div>
    <AppLoadingState
      v-else-if="pending"
      variant="inline"
      :title="text.loading"
    />
    <div
      v-else-if="error"
      class="py-12 text-center text-sm text-rose-600 dark:text-rose-300"
    >
      {{ text.loadError }}
    </div>
    <table
      v-else
      class="w-full border-collapse"
    >
      <thead>
        <tr class="border-b border-(--sk-border)">
          <th class="w-[240px] px-3 py-2 text-left whitespace-nowrap sk-label">
            디바이스
          </th>
          <th class="w-[120px] px-2 py-2 text-right whitespace-nowrap sk-label">
            recipe
          </th>
          <th class="w-[130px] px-2 py-2 text-right whitespace-nowrap sk-label">
            상한 초과
          </th>
          <th class="w-[92px] px-2 py-2" />
          <th class="w-full" />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="dev in deviceRows"
          :key="dev.lot_cd"
          class="border-t border-(--sk-border-soft) transition-colors hover:bg-(--sk-accent-soft)"
        >
          <td class="px-3 py-1.5 sk-value-num font-semibold">
            {{ dev.lot_cd }}
          </td>
          <td class="px-2 py-1.5 text-right sk-value-num">
            {{ dev.recipe_count }}
          </td>
          <td class="px-2 py-1.5 text-right">
            <span
              class="inline-flex h-6 min-w-8 items-center justify-center rounded-[var(--sk-r-chip)] border px-2 font-mono text-[12px] font-semibold whitespace-nowrap tabular-nums"
              :class="dev.violation_count > 0
                ? 'border-(--sk-bad-border) bg-(--sk-bad-soft) text-(--sk-bad)'
                : 'border-(--sk-border) bg-(--sk-muted-surface) text-(--sk-ink-muted)'"
              :title="violationTitle(dev)"
            >{{ formatViolations(dev) }}</span>
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
          <td />
        </tr>
      </tbody>
    </table>

    <EbeamDevstatDrillSlideover
      v-model:open="drillOpen"
      :device="activeDrill"
      highlight-label="상한 초과"
    />
  </div>
</template>

<script setup lang="ts">
import type { LotHealth, RecipeInput, RuleCell } from '~/utils/ruleEngine'
import { evaluateLot } from '~/utils/ruleEngine'
import { toViolationDrill, type DrillDevice } from '~/utils/deviceDrill'
import { groupRecipesByLot } from '~/utils/deviceProfile'
import { isExemptJob } from '~/utils/lotHealth'

const props = defineProps<{ cells: RuleCell[] }>()

const { fetchRecipeParams } = useDeviceStatisticsApi()
const { selectedDeviceLots } = useDeviceCart()

// Compliance is R3-only (D22). Filter the cart to R3 lots (lot_cd starts with 'R').
const r3Lots = computed(() => selectedDeviceLots.value.filter(lot => lot.startsWith('R')))

const text = {
  title: 'R3 룰 준수',
  legend: '선택한 R3 디바이스의 recipe 별 상한 준수 결과 · 상한을 넘긴 recipe / 룰로 판정한 recipe',
  details: '자세히',
  empty: '디바이스 통계에서 R3 디바이스를 선택하면 룰 준수 결과가 표시됩니다.',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.'
} as const

const { data, pending, error } = await useAsyncData<RecipeInput[]>(
  'r3-compliance',
  () => r3Lots.value.length ? fetchRecipeParams(r3Lots.value) : Promise.resolve([]),
  { watch: [r3Lots] }
)

const recipesByLot = computed(() => groupRecipesByLot(data.value ?? []))

/**
 * lot 하나의 판정 — **비교 페이지와 같은 모집단**으로.
 *
 * 두 화면이 같은 lot 에 다른 숫자를 말하던 자리입니다. 여기는 원본 recipe 를
 * 그대로 `evaluateLot` 에 넘기고 분모로 `recipes.length` 를 썼고, 비교 페이지의
 * Lot 요약은 특수 job 을 먼저 걷어낸 뒤 gray 를 뺀 `judged_recipes` 를 분모로
 * 썼습니다. 같은 lot 이 한쪽에서 `5 / 60`, 다른 쪽에서 `5 / 22` 로 보였고,
 * 분자가 같다는 것조차 우연처럼 읽혔습니다.
 *
 * 그래서 거르는 자리와 세는 분모를 `lotHealth.buildLotVerdicts` 에 맞춥니다.
 *
 *   특수 job(_*CDU/_FULL/_HALF/_MTX) — 분자·분모 **모두**에서 제외. 웨이퍼
 *     전면을 훑는 job 이라 애초에 상한이 겨냥한 recipe 가 아닙니다.
 *   gray(룰 미정 · 어노테이션 미설정) — 분모에서만 제외 (D14, 보수적).
 *
 * 남는 차이 하나는 **버킷**입니다. 이 화면에는 버킷 선택이 없어 늘 전 recipe 를
 * 봅니다 — 비교 페이지에서 좁은 버킷을 고르면 그쪽 숫자가 더 작은 것이 정상이고,
 * 아래 툴팁이 전체·판정·제외 건수를 함께 적어 그 차이를 눈으로 맞출 수 있게
 * 합니다.
 */
interface Judged {
  /** 특수 job 을 걷어낸 뒤의 recipe. drill 도 이 배열을 그대로 씁니다. */
  recipes: RecipeInput[]
  total: number
  exempt: number
  health: LotHealth
}

const judgedByLot = computed<Map<string, Judged>>(() => {
  const map = new Map<string, Judged>()
  for (const lot_cd of r3Lots.value) {
    const all = recipesByLot.value.get(lot_cd) ?? []
    const recipes = all.filter(r => !isExemptJob(r.recipe_id))
    map.set(lot_cd, {
      recipes,
      total: all.length,
      exempt: all.length - recipes.length,
      health: evaluateLot(lot_cd, recipes, props.cells)
    })
  }
  return map
})

interface ComplianceRow {
  lot_cd: string
  /** 받아온 recipe 전부 — 특수 job 을 포함합니다. 사라진 것이 없음을 보입니다. */
  recipe_count: number
  judged_count: number
  violation_count: number
  gray_count: number
  exempt_count: number
}

const deviceRows = computed<ComplianceRow[]>(() => {
  const rows: ComplianceRow[] = []
  for (const [lot_cd, j] of judgedByLot.value) {
    rows.push({
      lot_cd,
      recipe_count: j.total,
      judged_count: j.health.judged_recipes,
      violation_count: j.health.violation_recipes,
      gray_count: j.health.total_recipes - j.health.judged_recipes,
      exempt_count: j.exempt
    })
  }
  // 동률을 lot 이름으로 다시 가릅니다. 남겨 두면 순서가 카트 선택 순서에 딸려
  // 와, 아무것도 바꾸지 않고 다시 그려도 행이 자리를 바꿉니다.
  return rows.sort((a, b) => b.violation_count - a.violation_count || a.lot_cd.localeCompare(b.lot_cd))
})

/** 판정한 recipe 가 없으면 비율이 없습니다 — 0 / 0 은 "깨끗함" 으로 읽힙니다. */
const formatViolations = (row: ComplianceRow) =>
  row.judged_count === 0 ? '—' : `${row.violation_count} / ${row.judged_count}`

const violationTitle = (row: ComplianceRow) => {
  const parts = [`전체 recipe ${row.recipe_count}건`, `판정 ${row.judged_count}건`]
  if (row.gray_count > 0) parts.push(`룰·어노테이션 미정으로 판정 제외 ${row.gray_count}건`)
  if (row.exempt_count > 0) parts.push(`특수 job(CDU 계열/FULL/HALF/MTX) ${row.exempt_count}건은 판정 범위 밖`)
  const head = row.judged_count === 0
    ? '판정한 recipe 가 없습니다'
    : `상한을 넘긴 recipe ${row.violation_count}건 / 룰로 판정한 recipe ${row.judged_count}건`
  return `${head} — ${parts.join(' · ')}`
}

const drillOpen = ref(false)
const activeDrill = ref<DrillDevice | null>(null)

// 표가 이미 판정한 결과를 그대로 씁니다. 여기서 다시 `evaluateLot` 을 부르면
// 거르는 규칙이 두 곳에 생기고, 한쪽만 고친 날 배지 숫자와 표 숫자가 갈립니다.
const openDrill = (lot_cd: string) => {
  const judged = judgedByLot.value.get(lot_cd)
  if (!judged) return
  activeDrill.value = toViolationDrill(lot_cd, judged.recipes[0]?.ctn_desc ?? '', judged.health)
  drillOpen.value = true
}
</script>
