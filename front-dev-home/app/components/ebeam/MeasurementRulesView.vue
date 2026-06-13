<template>
  <div class="space-y-3">
    <EbeamMetaBar
      eyebrow="CD-SEM"
      :title="text.title"
      :subtitle="text.subtitle"
      :stats="metaStats"
    />

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
          :mfab="false"
        />
      </template>
    </div>

    <EbeamRulesComplianceTable
      v-if="version"
      :cells="version.cells"
    />
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import type { RuleVersion } from '~/utils/ruleEngine'

// Container for the measurement-rule editor (D13). Step 2 = read-only matrix;
// editing / monitor overlay / history land in steps 3–5.
const { setToolType } = useNavigation()
const { fetchRules } = useMeasurementRulesApi()

// R3-only rule page (D22 — M-fab placeholder caps removed). The rule API serves
// only R3; any other fab 404s.
const RULE_FAB = 'R3'

const text = {
  title: '계측 룰',
  subtitle: 'R3 계측 파라미터 cap 정책과 준수 결과를 확인합니다.',
  legendLead: '행 = 룰 셀 · 열 = 파라미터 타입 · 칸 = 최대 측정 포인트 수(cap, ≤).',
  legendCap: '상한',
  legendZero: '측정 금지',
  legendNA: '해당 없음',
  loading: '로딩 중',
  loadError: '룰을 불러오지 못했습니다.'
} as const

const { data: version, pending, error } = await useAsyncData<RuleVersion>(
  'measurement-rules',
  () => fetchRules(RULE_FAB)
)

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
