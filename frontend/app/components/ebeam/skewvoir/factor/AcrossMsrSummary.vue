<template>
  <div class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5">
    <!-- Pooled: every drawn MSR in one coefficient. -->
    <div class="flex flex-wrap items-stretch gap-2">
      <div
        v-for="stat in pooledStats"
        :key="stat.label"
        class="min-w-[5.5rem] flex-1 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2"
      >
        <p class="sk-label">
          {{ stat.label }}
        </p>
        <p
          class="mt-0.5 font-mono text-[15px] font-semibold tabular-nums"
          :class="stat.muted ? 'text-(--sk-ink-subtle)' : 'text-(--sk-ink)'"
        >
          {{ stat.value }}
        </p>
      </div>
    </div>

    <div
      v-if="result.pooled.reason"
      class="mt-2 flex items-center gap-1.5 rounded-(--sk-r-nav) bg-(--sk-chip-bg) px-2.5 py-1.5 text-[12px] text-(--sk-ink-subtle)"
    >
      <UIcon
        name="i-lucide-circle-slash"
        class="h-3.5 w-3.5 shrink-0"
      />
      <span>{{ result.pooled.reason }}</span>
    </div>

    <!-- Stratified: the SAME coefficient recomputed inside each tool. Shown
         beside the pooled one, never instead of it — a pooled sign that no
         single tool reproduces is the finding, and it is only visible when both
         are on screen (벤치마크 연구 §7.3). -->
    <div class="mt-3">
      <p class="sk-label">
        장비별 층화 상관
      </p>
      <p
        v-if="!result.strata.length"
        class="mt-1 sk-meta"
      >
        층화할 장비 정보가 없습니다.
      </p>
      <table
        v-else
        class="mt-1 w-full text-left"
      >
        <thead>
          <tr class="border-b border-(--sk-border-soft)">
            <th class="sk-label py-1 pr-2 font-normal">
              장비
            </th>
            <th class="sk-label py-1 pr-2 text-right font-normal">
              MSR N
            </th>
            <th class="sk-label py-1 pr-2 text-right font-normal">
              Pearson r
            </th>
            <th class="sk-label py-1 text-right font-normal">
              Spearman ρ
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="stratum in result.strata"
            :key="stratum.eqpId"
            class="border-b border-(--sk-border-soft) last:border-0"
          >
            <td class="py-1 pr-2">
              <span class="inline-flex items-center gap-1.5 sk-value">
                <span
                  class="size-2.5 shrink-0 rounded-full"
                  :style="{ backgroundColor: toolColor.get(stratum.eqpId) }"
                />
                {{ stratum.eqpId }}
              </span>
            </td>
            <td class="py-1 pr-2 text-right font-mono tabular-nums sk-value">
              {{ stratum.n }}
            </td>
            <!-- A suppressed stratum shows its reason in place of the two
                 coefficients, spanning both columns: an em dash alone would read
                 as "we did not look", not as "we declined to publish this". -->
            <td
              v-if="stratum.reason"
              colspan="2"
              class="py-1 text-right sk-meta"
            >
              {{ stratum.reason }}
            </td>
            <template v-else>
              <td class="py-1 pr-2 text-right font-mono tabular-nums sk-value">
                {{ fmt(stratum.pearson) }}
              </td>
              <td class="py-1 text-right font-mono tabular-nums sk-value">
                {{ fmt(stratum.spearman) }}
              </td>
            </template>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-2 flex flex-wrap gap-1.5">
      <!-- ALWAYS shown, exactly as in the single-scope summary: correlation is
           not causation (격차 보고서 §6 유지 항목). -->
      <span class="inline-flex items-center gap-1 rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 text-xs font-medium text-(--sk-ink-muted)">
        <UIcon
          name="i-lucide-info"
          class="h-3 w-3"
        />
        연관이며 원인 증명이 아님
      </span>
      <span class="inline-flex items-center gap-1 rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 text-xs font-medium text-(--sk-ink-muted)">
        <UIcon
          name="i-lucide-layers"
          class="h-3 w-3"
        />
        MSR 한 건 = 점 하나
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AcrossMsrResult } from '~/utils/skewvoirAnalysis/acrossMsr'
import { rankToolColors } from '~/utils/skewvoirAnalysis/toolColors'

const props = defineProps<{ result: AcrossMsrResult }>()

// Same ranking input as the scatter (the DRAWN points), so a tool's swatch here
// is the same color as its dots there. `''` — the "no tool identity" sentinel —
// is filtered for the same reason it is filtered there, and it has to be
// filtered in BOTH: a phantom entry shifts every named tool's rank by one, so
// dropping it on one side alone would paint one tool two different colors.
const toolColor = computed(() =>
  rankToolColors(props.result.points.map(p => p.eqpId).filter(Boolean))
)

const fmt = (v: number | null) => (v == null ? '—' : v.toFixed(3))

const pooledStats = computed(() => [
  { label: '전체 Pearson r', value: fmt(props.result.pooled.pearson), muted: props.result.pooled.pearson == null },
  { label: '전체 Spearman ρ', value: fmt(props.result.pooled.spearman), muted: props.result.pooled.spearman == null },
  { label: 'MSR N', value: String(props.result.pooled.n), muted: props.result.pooled.n === 0 },
  { label: '축 값 없어 제외', value: String(props.result.droppedN), muted: props.result.droppedN === 0 }
])
</script>
