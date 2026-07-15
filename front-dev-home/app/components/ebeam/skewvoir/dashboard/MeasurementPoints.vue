<template>
  <EbeamSkewvoirPanelFrame
    v-model="filter"
    title="Measurement Points"
    :meta="meta"
    :toggles="['전체', '이상·실패']"
    icon="i-lucide-list-ordered"
    body-class="flex flex-col"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex flex-1 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>

    <!-- 전체 — every measured point -->
    <div
      v-else-if="filter === '전체' && points.length"
      class="min-h-0 flex-1 overflow-auto"
    >
      <table class="w-full border-collapse text-[11.5px]">
        <thead class="sticky top-0 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            <th class="px-2 py-1.5 font-medium">
              #
            </th>
            <th class="px-2 py-1.5 font-medium">
              CHIP XY
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              DATA
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              RADIUS (mm)
            </th>
            <th class="px-2 py-1.5 font-medium">
              SEQ
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in points"
            :key="p.key"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0"
            :class="p.seq === analysis.focusedSequence.value ? 'bg-(--sk-brand)/12' : 'hover:bg-(--sk-chip-bg)'"
            @click="analysis.setFocusedSequence(p.seq)"
          >
            <td class="px-2 py-1.5 font-mono text-(--sk-ink-subtle)">
              {{ p.mp }}
            </td>
            <td class="px-2 py-1.5 font-mono text-zinc-700 dark:text-zinc-300">
              {{ p.chip }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-zinc-800 dark:text-zinc-100">
              {{ p.cd.toFixed(2) }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-(--sk-ink-muted)">
              {{ p.radius.toFixed(2) }}
            </td>
            <td class="px-2 py-1.5 font-mono text-(--sk-ink-subtle)">
              {{ p.seq }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 이상·실패 — the single overview source: flagged + failed sites -->
    <div
      v-else-if="filter === '이상·실패' && verdictRows.length"
      class="min-h-0 flex-1 overflow-auto"
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
            v-for="r in verdictRows"
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
      <p class="px-2 py-2 font-mono text-[10px] text-(--sk-ink-subtle)">
        실패 사이트는 통계에서 제외됩니다 — 평균·σ·3Σ 어디에도 포함되지 않습니다.
      </p>
    </div>

    <!-- Empty states -->
    <div
      v-else
      class="flex flex-1 items-center justify-center px-3 text-center text-[12px] text-(--sk-ink-subtle)"
    >
      {{ emptyLabel }}
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { SiteKind } from '~/utils/overview'
import { measuredRows } from '~/utils/msrRows'
import { siteRadiusMm } from '~/utils/waferGeometry'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const filter = ref<'전체' | '이상·실패'>('전체')

const points = computed(() =>
  measuredRows(props.analysis.siteRows.value)
    .filter(r => r.parameter === props.analysis.activeParam.value)
    .map((r, i) => ({
      key: `${r.msr}-${r.sequence}-${i}`,
      mp: r.mp_number,
      chip: r.chip_number,
      cd: r.cd_value,
      radius: siteRadiusMm(r.stage_coordinate, props.analysis.waferGeo.value) ?? 0,
      seq: r.sequence
    }))
)

// The flagged + failed rows from the single overview source (SiteVerdicts data).
const verdictRows = computed(() => props.analysis.activeOverview.value.tableRows)
const unit = computed(() => props.analysis.activeUnit.value)

const meta = computed(() =>
  filter.value === '전체'
    ? `${points.value.length} sites`
    : `${verdictRows.value.length} 이상·실패`
)

const emptyLabel = computed(() => {
  if (filter.value === '전체') return `${props.analysis.activeParam.value} 측정점이 없습니다.`
  return props.analysis.activeOverview.value.status === 'evaluated'
    ? '이상·실패 사이트가 없습니다.'
    : '측정 site 부족 — 이상 평가 불가'
})

const badgeLabel = (kind: SiteKind) =>
  kind === 'abnormal' ? '이상' : kind === 'watch' ? '주의' : '측정 실패'

const badgeClass = (kind: SiteKind) =>
  kind === 'abnormal'
    ? 'bg-(--sk-bad-soft) text-(--sk-bad)'
    : kind === 'watch'
      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
      : 'bg-(--sk-chip-bg) text-(--sk-ink-subtle)'
</script>
