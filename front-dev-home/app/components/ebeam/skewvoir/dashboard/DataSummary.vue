<template>
  <EbeamSkewvoirPanelFrame
    title="파라미터"
    :meta="meta"
    icon="i-lucide-table-2"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex h-40 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>
    <div
      v-else-if="rows.length"
      class="overflow-auto"
    >
      <table class="w-full border-collapse text-[11.5px]">
        <thead class="sticky top-0 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            <th class="px-2 py-1.5 font-medium">
              PARAMETER
            </th>
            <th class="px-2 py-1.5 font-medium">
              COVERAGE
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              MEAN
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              3Σ
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              OUT
            </th>
            <th class="px-2 py-1.5 font-medium">
              UNIT
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in rows"
            :key="r.parameter"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0"
            :class="r.parameter === analysis.activeParam.value ? 'bg-(--sk-brand)/8 font-medium' : 'hover:bg-(--sk-chip-bg)'"
            :aria-selected="r.parameter === analysis.activeParam.value"
            @click="analysis.setParam(r.parameter)"
          >
            <td class="px-2 py-1.5 font-mono text-zinc-800 dark:text-zinc-100">
              {{ r.parameter }}
            </td>
            <td
              class="px-2 py-1.5 font-mono tabular-nums"
              :class="r.failed > 0 ? 'text-(--sk-bad)' : 'text-(--sk-ink-muted)'"
            >
              {{ r.measured }}/{{ r.total }}<span
                v-if="r.failed > 0"
                class="text-[10px]"
              > · {{ r.failed }} 실패</span>
            </td>
            <td
              class="px-2 py-1.5 text-right font-mono tabular-nums text-zinc-700 dark:text-zinc-300"
            >
              {{ r.mean.toFixed(3) }}
            </td>
            <td
              class="px-2 py-1.5 text-right font-mono tabular-nums text-zinc-700 dark:text-zinc-300"
            >
              {{ (r.std * 3).toFixed(3) }}
            </td>
            <td
              class="px-2 py-1.5 text-right font-mono tabular-nums"
              :class="r.outlier > 0 ? 'text-(--sk-bad)' : 'text-(--sk-ink-subtle)'"
            >
              {{ r.evaluated ? r.outlier : '—' }}
            </td>
            <td
              class="px-2 py-1.5 font-mono text-(--sk-ink-subtle)"
            >
              {{ r.unit }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div
      v-else
      class="flex h-40 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      파라미터 요약이 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// One row per parameter: backend summary (mean/std/unit) joined with the honest
// per-parameter coverage + outlier count from overviewFor(). The OUT column shows
// '—' when the parameter can't be judged (status insufficient) — never a fake 0.
const rows = computed(() =>
  props.analysis.paramSummaries.value.map((s) => {
    const ov = props.analysis.overviewFor(s.parameter)
    return {
      parameter: s.parameter,
      mean: s.mean,
      std: s.std,
      unit: s.unit,
      total: ov.coverage.total,
      measured: ov.coverage.measured,
      failed: ov.coverage.failed,
      outlier: ov.outlierCount,
      evaluated: ov.status === 'evaluated'
    }
  })
)

const meta = computed(() => `${rows.value.length} parameters`)
</script>
