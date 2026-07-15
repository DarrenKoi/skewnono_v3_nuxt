<template>
  <div class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h3 class="sk-title">
          Next PM focus ranking
        </h3>
        <span class="sk-meta">
          Tools past the line, worst {{ focusN }} per beam
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
          {{ beam }} line
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
          <span class="font-mono text-[10px] text-(--sk-ink-muted)">
            line {{ (threshold[beam] ?? 0).toFixed(2) }}nm
          </span>
        </div>

        <div
          v-if="!rankedByBeam[beam]?.length"
          class="rounded-lg border border-dashed border-(--sk-border) px-3 py-4 text-center text-[11px] text-(--sk-ink-muted)"
        >
          No tool crosses the line — this beam has converged.
        </div>

        <ul
          v-else
          class="space-y-1"
        >
          <li
            v-for="(row, index) in rankedByBeam[beam]"
            :key="`${beam}:${row.eqp_id}`"
          >
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-(--sk-muted-surface)"
              :class="isSelected(beam, row.eqp_id) ? 'ring-1 ring-(--sk-accent)' : ''"
              @click="emit('select', { beam, eqpId: row.eqp_id })"
            >
              <span class="w-5 shrink-0 font-mono text-[11px] text-(--sk-ink-muted)">
                {{ index + 1 }}
              </span>
              <span class="w-[8rem] shrink-0 truncate sk-value-num">
                {{ row.eqp_id }}
              </span>
              <span class="relative h-4 flex-1 overflow-hidden rounded bg-(--sk-border-soft)">
                <span
                  class="absolute inset-y-0 left-0 rounded bg-red-500/75"
                  :style="{ width: barWidth(beam, row.score) }"
                />
              </span>
              <span class="w-[3.25rem] shrink-0 text-right font-mono text-[11px] tabular-nums text-red-600 dark:text-red-400">
                {{ row.score.toFixed(2) }}
              </span>
              <span class="w-5 shrink-0 text-center font-mono text-[10px] text-(--sk-ink-muted)">
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
  selected: { beam: BeamCondition, eqpId: string } | null
}>()

const emit = defineEmits<{
  'update:focusN': [value: number]
  'update:threshold': [payload: { beam: BeamCondition, value: number }]
  'select': [payload: { beam: BeamCondition, eqpId: string }]
}>()

const focusNOptions = ['1', '2', '3', '4', '5', '6', '7', '8']

// The self-limiting gate: only tools whose max-axis skew exceeds the per-beam
// nm threshold are candidates; the worst `focusN` of those are nominated. A
// converged beam yields an empty list (the "this beam has converged" message).
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

const isSelected = (beam: BeamCondition, eqpId: string) =>
  props.selected?.beam === beam && props.selected?.eqpId === eqpId
</script>
