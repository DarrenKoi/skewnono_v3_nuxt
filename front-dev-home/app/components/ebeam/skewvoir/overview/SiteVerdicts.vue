<template>
  <EbeamSkewvoirPanelFrame
    title="이상 / 실패 사이트"
    :meta="meta"
    icon="i-lucide-alert-triangle"
  >
    <div
      v-if="tableRows.length"
      class="overflow-auto"
    >
      <table class="w-full border-collapse text-[11.5px]">
        <thead class="sticky top-0 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            <th class="px-2 py-1.5 font-medium">
              SEQ
            </th>
            <th class="px-2 py-1.5 font-medium">
              CHIP
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              CD ({{ unit }})
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              Δ vs sites
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              판정
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in tableRows"
            :key="r.sequence"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0"
            :class="[
              r.kind === 'failed' ? 'text-(--sk-ink-subtle)' : '',
              r.sequence === analysis.focusedSequence.value ? 'bg-(--sk-brand)/12' : 'hover:bg-(--sk-chip-bg)'
            ]"
            @click="analysis.setFocusedSequence(r.sequence)"
          >
            <td class="px-2 py-1.5 font-mono">
              {{ r.sequence }}
            </td>
            <td class="px-2 py-1.5 font-mono">
              {{ r.chip }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums">
              {{ r.cd != null ? r.cd.toFixed(2) : '—' }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums">
              {{ r.delta != null ? `${r.delta > 0 ? '+' : ''}${r.delta.toFixed(1)}%` : '—' }}
            </td>
            <td class="px-2 py-1.5 text-right">
              <span
                class="rounded-(--sk-r-chip) px-1.5 py-0.5 font-mono text-[10px]"
                :class="badgeClass(r.kind)"
              >{{ badgeLabel(r.kind) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="px-2 pt-2 font-mono text-[10px] text-(--sk-ink-subtle)">
        실패 사이트는 통계에서 제외됩니다 — 평균·σ·3Σ 어디에도 포함되지 않습니다.
      </p>
    </div>
    <div
      v-else
      class="flex h-40 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      {{ analysis.activeOverview.value.status === 'evaluated'
        ? '이상·실패 사이트가 없습니다.'
        : '측정 site 부족 — 이상 평가 불가' }}
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { SiteKind } from '~/utils/overview'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const tableRows = computed(() => props.analysis.activeOverview.value.tableRows)
const unit = computed(() => props.analysis.activeUnit.value)
const meta = computed(() => `${tableRows.value.length} sites`)

const badgeLabel = (kind: SiteKind) =>
  kind === 'abnormal'
    ? '이상'
    : kind === 'watch'
      ? '주의'
      : '측정 실패'

const badgeClass = (kind: SiteKind) =>
  kind === 'abnormal'
    ? 'bg-(--sk-bad-soft) text-(--sk-bad)'
    : kind === 'watch'
      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
      : 'bg-(--sk-chip-bg) text-(--sk-ink-subtle)'
</script>
