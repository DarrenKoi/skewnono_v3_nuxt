<template>
  <div class="space-y-3">
    <EbeamMetaBar
      eyebrow="CD-SEM"
      :title="text.title"
      :subtitle="text.subtitle"
      :stats="metaStats"
    >
      <template #toggle>
        <EbeamRulesFabSelector
          v-model="selectedFab"
          :fabs="fabs"
        />
      </template>
    </EbeamMetaBar>

    <div class="dashboard-surface rounded-2xl p-4">
      <!-- legend -->
      <div class="mb-3 flex flex-wrap items-center gap-4 text-[11.5px] text-(--sk-ink-muted)">
        <span>{{ text.legendLead }}</span>
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-flex h-5 min-w-7 items-center justify-center rounded border border-(--sk-border) bg-(--sk-surface) font-mono text-[11px] text-(--sk-ink)">13</span>
          {{ text.legendCap }}
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-flex h-5 min-w-7 items-center justify-center rounded border border-(--sk-border) bg-(--sk-surface) font-mono text-[11px] text-(--sk-ink-subtle)">0</span>
          {{ text.legendZero }}
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-flex h-5 min-w-7 items-center justify-center rounded border border-dashed border-(--sk-border) font-mono text-[11px] text-(--sk-ink-subtle)">—</span>
          {{ text.legendNA }}
        </span>
      </div>

      <div
        v-if="pending"
        class="flex items-center justify-center gap-2 py-16 text-sm text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        {{ text.loading }}
      </div>
      <div
        v-else-if="error"
        class="py-16 text-center text-sm text-rose-600 dark:text-rose-300"
      >
        {{ text.loadError }}
      </div>
      <template v-else-if="version">
        <EbeamRulesMatrix
          :cells="version.cells"
          :mfab="isMfab"
        />
        <p
          v-if="isMfab"
          class="mt-3 text-[11.5px] text-(--sk-ink-subtle)"
        >
          {{ text.mfabNote }}
        </p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import type { RuleVersion } from '~/utils/ruleEngine'

// Container for the measurement-rule editor (D13). Step 2 = read-only matrix;
// editing / monitor overlay / history land in steps 3–5.
const { setToolType } = useNavigation()
const { fetchRules } = useMeasurementRulesApi()

// R3 (full dev matrix) first, then M-fabs newest-first — matches device-statistics.
// Display order is a frontend concern; the seeded set is rules.py:M_FAB_IDS (+R3).
// Keep in sync when adding a fab there (a /rules/fabs route can serve it later).
const fabs = ['R3', 'M16', 'M15', 'M14', 'M12', 'M11']
const DEFAULT_FAB = 'R3'
const STORAGE_KEY = 'skewnono:measurementRules.selectedFab'

const readSavedFab = (): string => {
  if (typeof window === 'undefined') return DEFAULT_FAB
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return saved && fabs.includes(saved) ? saved : DEFAULT_FAB
  } catch {
    return DEFAULT_FAB
  }
}

const selectedFab = ref<string>(readSavedFab())
const isMfab = computed(() => selectedFab.value !== 'R3')

const text = {
  title: '계측 룰',
  subtitle: 'Fab 별 계측 파라미터 cap 정책을 확인합니다.',
  legendLead: '행 = 룰 셀 · 열 = 파라미터 타입 · 칸 = 최대 측정 포인트 수(cap, ≤).',
  legendCap: '상한',
  legendZero: '측정 금지',
  legendNA: '해당 없음',
  loading: '로딩 중',
  loadError: '룰을 불러오지 못했습니다.',
  mfabNote: '▲ 양산 fab — family/phase/Pool 축 없이 Recipe Class × memory_class(DRAM/NAND) 룰입니다.'
} as const

// Stable key + watch (the device-statistics convention) — one cache slot the
// matrix reuses; switching fab refetches in place rather than spawning per-fab keys.
const { data: version, pending, error } = await useAsyncData<RuleVersion>(
  'measurement-rules',
  () => fetchRules(selectedFab.value),
  { watch: [selectedFab] }
)

const metaStats = computed<MetaBarStat[]>(() => {
  if (!version.value) return []
  return [
    { key: 'cells', label: '룰 셀', value: version.value.cells?.length ?? 0, tone: 'neutral' },
    { key: 'version', label: '버전', value: `v${version.value.version}`, tone: 'accent' },
    { key: 'editor', label: '최종 편집', value: version.value.edited_by, tone: 'neutral' }
  ]
})

watch(selectedFab, (next) => {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, next)
  } catch { /* noop */ }
})

onMounted(() => {
  setToolType('cd-sem')
})
</script>
