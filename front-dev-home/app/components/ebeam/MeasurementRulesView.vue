<template>
  <div class="space-y-2.5">
    <EbeamMetaBar
      eyebrow="CD-SEM"
      :title="text.title"
      :subtitle="text.subtitle"
      :stats="metaStats"
    />

    <div class="dashboard-surface rounded-2xl p-3">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 class="sk-title">
          {{ text.mainTitle }}
        </h3>
        <span class="sk-meta">
          {{ text.mainHint }}
        </span>
      </div>

      <!-- fixed caps + legend -->
      <div class="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 sk-meta">
        <span
          v-if="fixedEntries.length > 0"
          class="inline-flex items-center gap-1.5"
        >
          {{ text.fixedLead }}
          <span
            v-for="fixed in fixedEntries"
            :key="fixed.key"
            class="inline-flex h-5 items-center gap-1 rounded border border-(--sk-border) bg-(--sk-surface) px-1.5 font-mono text-[11px] text-(--sk-ink)"
          >{{ fixed.key }} <b class="font-semibold">{{ fixed.value }}</b></span>
          {{ text.fixedNote }}
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-flex h-5 min-w-7 items-center justify-center rounded border border-(--sk-border) bg-(--sk-surface) font-mono text-[11px] text-(--sk-ink)">9</span>
          {{ text.legendCap }}
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-flex h-5 min-w-7 items-center justify-center rounded border border-(--sk-border) bg-(--sk-surface) font-mono text-[11px] text-(--sk-ink-subtle)">0</span>
          {{ text.legendZero }}
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-flex h-5 min-w-7 items-center justify-center rounded border border-(--sk-accent-border) bg-(--sk-accent-tint) font-mono text-[11px] text-(--sk-accent)">16</span>
          {{ text.legendExpanded }}
        </span>
      </div>

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
        class="py-16 text-center text-sm text-rose-600 dark:text-rose-300"
      >
        {{ text.loadError }}
      </div>
      <EbeamRulesMatrix
        v-else-if="version"
        :cells="mainCells"
      />
    </div>

    <EbeamRulesSampleTable
      v-if="version"
      :cells="sampleCells"
    />

    <EbeamRulesComplianceTable
      v-if="version"
      :cells="version.cells"
    />
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import type { RuleVersion } from '~/utils/ruleEngine'
import { fixedCaps } from '~/utils/ruleMatrix'

// Container for the measurement-rule editor (D13). Step 2 = read-only matrix;
// editing / monitor overlay / history land in steps 3–5.
// Display split: WAFER·LEVEL are fab-wide constants → one fixed strip; the
// vehicle axis collapses to EV(포함 이전)/TV(포함 이후); Sample rules get their
// own table so the Main story (TV opens up EDGE/EDGE_EX) stays readable.
const { setToolType } = useNavigation()
const { fetchRules } = useMeasurementRulesApi()

// R3-only rule page (D22 — M-fab placeholder caps removed). The rule API serves
// only R3; any other fab 404s.
const RULE_FAB = 'R3'

const text = {
  title: '계측 룰',
  subtitle: 'R3 계측 파라미터 cap 정책과 준수 결과를 확인합니다.',
  mainTitle: 'Main 룰',
  mainHint: '칸 = 최대 측정 포인트 수(cap, ≤) · EV = EV 포함 이전 · TV = TV 포함 이후',
  fixedLead: '고정 cap',
  fixedNote: '모든 룰 공통 · 변경 없음',
  legendCap: '상한',
  legendZero: '측정 금지',
  legendExpanded: 'EDGE·EDGE_EX 확대 (TV 포함 이후 · 수율 후)',
  loading: '로딩 중',
  loadError: '룰을 불러오지 못했습니다.'
} as const

const { data: version, pending, error } = await useAsyncData<RuleVersion>(
  'measurement-rules',
  () => fetchRules(RULE_FAB)
)

const mainCells = computed(() =>
  (version.value?.cells ?? []).filter(cell => cell?.selector?.recipe_class === 'Main')
)
const sampleCells = computed(() =>
  (version.value?.cells ?? []).filter(cell => cell?.selector?.recipe_class === 'Sample')
)

// WAFER 13 · LEVEL 4 — identical on every cell, so shown once instead of as columns.
const fixedEntries = computed(() => fixedCaps(version.value?.cells ?? []))

const metaStats = computed<MetaBarStat[]>(() => {
  if (!version.value) return []
  return [
    { key: 'cells', label: '룰 셀', value: version.value.cells?.length ?? 0, tone: 'neutral' },
    { key: 'version', label: '버전', value: `v${version.value.version}`, tone: 'accent' },
    { key: 'editor', label: '최종 편집', value: version.value.edited_by, tone: 'neutral' }
  ]
})

onMounted(() => {
  setToolType('cd-sem')
})
</script>
