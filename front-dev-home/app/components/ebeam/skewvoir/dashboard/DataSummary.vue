<template>
  <EbeamSkewvoirPanelFrame
    title="Data Summary"
    :meta="meta"
    icon="i-lucide-table-2"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex h-72 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>
    <div
      v-else-if="summaries.length"
      class="max-h-72 overflow-auto"
    >
      <table class="w-full border-collapse text-[11.5px]">
        <thead class="sticky top-0 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            <th class="px-2 py-1.5 font-medium">
              MP NAME
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              MEAN
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              MAX
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              MIN
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              3Σ
            </th>
            <th class="px-2 py-1.5 font-medium">
              UNIT
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in summaries"
            :key="s.parameter"
            class="border-b border-(--sk-border-soft) last:border-0"
            :class="s.parameter === analysis.activeParam.value ? 'bg-(--sk-brand)/8 font-medium' : ''"
          >
            <td class="px-2 py-1.5 font-mono text-zinc-800 dark:text-zinc-100">
              {{ s.parameter }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-zinc-700 dark:text-zinc-300">
              {{ s.mean.toFixed(4) }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-(--sk-ink-muted)">
              {{ s.max.toFixed(2) }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-(--sk-ink-muted)">
              {{ s.min.toFixed(2) }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-zinc-700 dark:text-zinc-300">
              {{ (s.std * 3).toFixed(4) }}
            </td>
            <td class="px-2 py-1.5 font-mono text-(--sk-ink-subtle)">
              {{ s.unit }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div
      v-else
      class="flex h-72 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      파라미터 요약이 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const summaries = computed(() => props.analysis.paramSummaries.value)
const meta = computed(() => {
  const s = props.analysis.activeSummary.value
  return `${summaries.value.length} parameters${s ? ` · μ ${s.mean.toFixed(3)}` : ''}`
})
</script>
