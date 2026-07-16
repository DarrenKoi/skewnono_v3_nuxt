<template>
  <EbeamSkewvoirPanelFrame
    title="Sector Profile"
    :meta="meta"
    icon="i-lucide-compass"
    body-class="flex flex-col gap-2"
  >
    <div
      v-if="summary.status === 'unavailable'"
      class="flex flex-1 flex-col items-center justify-center gap-1 px-4 text-center sk-body"
    >
      <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 font-mono text-[11px] font-semibold text-(--sk-ink-muted)">평가 불가</span>
      <span class="text-[11px] text-(--sk-ink-subtle)">{{ summary.reason }}</span>
    </div>
    <template v-else>
      <p class="sk-meta">
        노치 기준: {{ notchLabel }}<span class="text-(--sk-ink-subtle)"> · Phase-1 검증 기본값</span>
      </p>
      <table class="w-full border-collapse text-xs">
        <caption class="sr-only">
          {{ ariaSummary }}
        </caption>
        <thead>
          <tr class="border-b border-(--sk-border) font-mono text-[11px] text-(--sk-ink-muted)">
            <th
              scope="col"
              class="px-1.5 py-1 text-left font-semibold"
            >
              섹터
            </th>
            <th
              scope="col"
              class="px-1.5 py-1 text-right font-semibold"
            >
              median
            </th>
            <th
              scope="col"
              class="px-1.5 py-1 text-right font-semibold"
            >
              IQR
            </th>
            <th
              scope="col"
              class="px-1.5 py-1 text-right font-semibold"
            >
              N
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in summary.sectors"
            :key="s.key"
            class="border-b border-(--sk-border-soft) last:border-0"
          >
            <td class="px-1.5 py-1 font-medium text-(--sk-ink)">
              {{ s.label }}
            </td>
            <td class="px-1.5 py-1 text-right font-mono tabular-nums">
              {{ s.median.toFixed(3) }}
            </td>
            <td class="px-1.5 py-1 text-right font-mono tabular-nums text-(--sk-ink-muted)">
              {{ s.spread.toFixed(3) }}
            </td>
            <td class="px-1.5 py-1 text-right font-mono tabular-nums">
              {{ s.count }}
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SpatialResult, NotchOrientation } from '~/utils/skewvoirAnalysis/spatial'

const props = defineProps<{
  spatial: SpatialResult
  unit: string
}>()

const summary = computed(() => props.spatial.sectors)

const NOTCH_LABEL: Record<NotchOrientation, string> = {
  bottom: '하단(bottom)',
  top: '상단(top)',
  left: '좌측(left)',
  right: '우측(right)'
}
const notchLabel = computed(() => NOTCH_LABEL[summary.value.notch])

const meta = computed(() =>
  summary.value.status === 'ok' ? `${summary.value.sectors.length} sectors · ${props.unit}` : '평가 불가'
)

// This panel renders a data table, not a canvas chart — the caption below is
// the screen-reader summary of its headline numbers (no role="img" needed
// since the table markup is already accessible).
const ariaSummary = computed(() => {
  if (summary.value.status !== 'ok') return `섹터 프로파일: 평가 불가 (${summary.value.reason})`
  const parts = summary.value.sectors.map(s => `${s.label} ${s.median.toFixed(2)}${props.unit}`).join(', ')
  return `섹터 프로파일: ${summary.value.sectors.length}개 섹터, 노치 기준 ${notchLabel.value} — ${parts}`
})
</script>
