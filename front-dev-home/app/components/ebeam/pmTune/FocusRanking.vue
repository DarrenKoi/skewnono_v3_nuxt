<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <p class="sk-title">
          다음 PM 후보 랭킹
        </p>
        <span class="sk-meta">
          기준선을 넘은 장비, beam별 최악 {{ focusN }}대
        </span>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <label class="flex items-center gap-1.5 sk-label">
          N
          <USelect
            :model-value="String(focusN)"
            :items="focusNOptions"
            size="xs"
            class="w-[4.5rem]"
            @update:model-value="(value: string) => emit('update:focusN', Number(value))"
          />
        </label>

        <label
          v-for="beam in beamConditions"
          :key="beam"
          class="flex items-center gap-1.5 sk-label"
        >
          {{ beam }} 기준선
          <UInput
            :model-value="String(threshold[beam] ?? 0)"
            size="xs"
            type="number"
            min="0"
            step="0.05"
            class="w-[5rem]"
            @update:model-value="(value: string) => updateThreshold(beam, value)"
          />
          <span class="font-mono">nm</span>
        </label>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <section
        v-for="beam in beamConditions"
        :key="beam"
      >
        <div class="mb-1.5 flex items-center gap-2">
          <span class="sk-title">{{ beam }}</span>
          <span class="font-mono text-xs tabular-nums text-(--sk-ink-muted)">
            기준선 {{ (threshold[beam] ?? 0).toFixed(2) }} nm
          </span>
        </div>

        <div
          v-if="!rankedByBeam[beam]?.length"
          class="rounded-lg border border-dashed border-(--sk-border) px-3 py-4 text-center sk-field-label"
        >
          기준선을 넘는 장비가 없습니다 — 이 beam은 수렴 상태입니다.
        </div>

        <ul
          v-else
          class="space-y-1"
        >
          <li
            v-for="(row, index) in rankedByBeam[beam]"
            :key="`${beam}:${row.eqp_id}`"
          >
            <!-- Clicking a nominee PICKS it — the ranking is this page's entry
                 point into "which tool goes to PM next", and the picked tool is
                 what every other card argues about. -->
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-(--sk-muted-surface)"
              :class="row.eqp_id === picked ? 'ring-1 ring-(--sk-accent)' : ''"
              @click="emit('pick', row.eqp_id)"
            >
              <span class="w-5 shrink-0 font-mono text-xs text-(--sk-ink-muted)">
                {{ index + 1 }}
              </span>
              <span class="w-[8rem] shrink-0 truncate sk-value-num">
                {{ row.eqp_id }}
              </span>
              <span class="relative h-4 flex-1 overflow-hidden rounded bg-(--sk-border-soft)">
                <span
                  class="absolute inset-y-0 left-0 rounded bg-(--sk-bad) opacity-75"
                  :style="{ width: barWidth(beam, row.score) }"
                />
              </span>
              <span class="w-[3.25rem] shrink-0 text-right font-mono text-xs tabular-nums text-(--sk-bad)">
                {{ row.score.toFixed(2) }}
              </span>
              <span class="w-5 shrink-0 text-center font-mono text-xs text-(--sk-ink-muted)">
                {{ row.axis }}
              </span>
            </button>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ToolBlock } from '~/composables/usePmPlanningApi'
import { rankFocusTargets, type BeamCondition, type RankedTool } from '~/utils/pmPlanning'

const props = defineProps<{
  tools: ToolBlock[]
  beamConditions: BeamCondition[]
  focusN: number
  threshold: Record<string, number>
  picked: string | null
}>()

const emit = defineEmits<{
  'update:focusN': [value: number]
  'update:threshold': [payload: { beam: BeamCondition, value: number }]
  'pick': [eqpId: string]
}>()

const focusNOptions = ['1', '2', '3', '4', '5', '6', '7', '8']

// The self-limiting gate: only tools whose max-axis skew exceeds the per-beam
// nm threshold are candidates; the worst `focusN` of those are nominated. A
// converged beam yields an empty list (the "수렴 상태" message).
const rankedByBeam = computed<Record<string, RankedTool[]>>(() => {
  const groups: Record<string, RankedTool[]> = {}
  for (const beam of props.beamConditions) {
    groups[beam] = rankFocusTargets(props.tools, beam, props.threshold[beam] ?? 0, props.focusN)
  }
  return groups
})

// Bar fills relative to the worst nominee in that beam so the strip reads full.
const barWidth = (beam: BeamCondition, score: number): string => {
  const rows = rankedByBeam.value[beam] ?? []
  const max = rows[0]?.score ?? 1
  return `${Math.max(6, Math.round((score / max) * 100))}%`
}

const updateThreshold = (beam: BeamCondition, value: string) => {
  const next = Number(value)
  if (!Number.isFinite(next)) return
  emit('update:threshold', { beam, value: Math.max(0, next) })
}
</script>
