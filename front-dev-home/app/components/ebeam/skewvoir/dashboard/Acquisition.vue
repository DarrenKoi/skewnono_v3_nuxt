<template>
  <EbeamSkewvoirPanelFrame
    title="측정 조건 & 정렬"
    :meta="meta"
    icon="i-lucide-settings-2"
  >
    <div class="grid gap-3 md:grid-cols-2">
      <dl class="space-y-1.5 text-[11.5px]">
        <div
          v-for="f in conditionFields"
          :key="f.label"
          class="flex items-baseline justify-between gap-2 border-b border-(--sk-border-soft) pb-1"
        >
          <dt class="text-(--sk-ink-muted)">
            {{ f.label }}
          </dt>
          <dd class="truncate font-mono text-zinc-800 dark:text-zinc-200">
            {{ f.value }}
          </dd>
        </div>
      </dl>
      <div class="space-y-1.5 text-[11.5px]">
        <div
          v-for="a in alignRows"
          :key="a.key"
          class="flex items-baseline justify-between gap-2 border-b border-(--sk-border-soft) pb-1"
        >
          <dt class="font-mono text-(--sk-ink-muted)">
            {{ a.key }}
          </dt>
          <dd class="truncate font-mono text-zinc-800 dark:text-zinc-200">
            {{ a.method }} · {{ a.offset }} <span class="text-(--sk-ink-subtle)">[{{ a.score }}]</span>
          </dd>
        </div>
        <p class="pt-0.5 font-mono text-[10px] text-(--sk-ink-subtle)">
          score: 모니터링만 · 비교 불가
        </p>
      </div>
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { measuredRows } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const info = computed(() => props.analysis.focusFile.value?.exe_detail_info ?? null)
// Representative measurement conditions: mag/vac/pixel are constant across a run,
// so the first measured row for the active parameter is representative.
const cond = computed(() =>
  measuredRows(props.analysis.siteRows.value).find(r => r.parameter === props.analysis.activeParam.value) ?? null
)

const conditionFields = computed(() => [
  { label: 'Wafer', value: info.value?.wafer_id ?? '—' },
  { label: 'Process', value: info.value?.process ?? '—' },
  { label: 'Mag', value: cond.value ? `${cond.value.meas_condition_mag.toLocaleString()} ×` : '—' },
  { label: 'Vacc', value: cond.value ? `${cond.value.meas_condition_vac} V` : '—' },
  { label: 'Pixel', value: cond.value?.meas_condition_pixel ?? '—' }
])

// alignment.offset is keyed (e.g. '1'/'2'/'3') → [method, x, y]; score is keyed the same.
const alignRows = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  if (!a) return []
  return Object.entries(a.offset).map(([key, tuple]) => ({
    key: `ALIGN ${key}`,
    method: tuple[0],
    offset: `${tuple[1]}, ${tuple[2]}`,
    score: a.score[key] ?? '—'
  }))
})

const meta = computed(() => props.analysis.focusFile.value?.exe_detail_info?.recipe_name ?? '—')
</script>
