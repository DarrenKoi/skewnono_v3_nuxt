<template>
  <div class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h3 class="text-[12.5px] font-semibold text-(--sk-ink)">
          Next PM focus ranking
        </h3>
        <span class="text-[10.5px] text-(--sk-ink-muted)">
          Top {{ topN }} per beam, colored by relative skew
        </span>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <label class="flex items-center gap-1.5 text-[11px] text-(--sk-ink-muted)">
          N
          <USelect
            :model-value="String(topN)"
            :items="topNOptions"
            size="xs"
            class="w-[4.5rem]"
            @update:model-value="(value: string) => emit('update:topN', Number(value))"
          />
        </label>

        <label class="flex items-center gap-1.5 text-[11px] text-(--sk-ink-muted)">
          Focus line
          <UInput
            :model-value="String(thresholdPct)"
            size="xs"
            type="number"
            min="1"
            max="100"
            step="5"
            class="w-[5.5rem]"
            @update:model-value="updateThresholdPct"
          />
          <span class="font-mono">%</span>
        </label>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <section
        v-for="beam in beamGroups"
        :key="beam"
      >
        <div class="mb-1.5 flex items-center gap-2">
          <span class="text-[12px] font-semibold text-(--sk-ink)">{{ beam }}</span>
          <span class="font-mono text-[10px] text-(--sk-ink-muted)">
            focus >= {{ thresholdPct }}%
          </span>
        </div>

        <div
          v-if="!rankedByBeam[beam]?.length"
          class="rounded-lg border border-dashed border-(--sk-border) px-3 py-4 text-center text-[11px] text-(--sk-ink-muted)"
        >
          No ranked tools for this beam.
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
              :class="row.eqp_id === selectedToolId ? 'ring-1 ring-(--sk-accent)' : ''"
              @click="emit('select-tool', row.eqp_id)"
            >
              <span class="w-5 shrink-0 font-mono text-[11px] text-(--sk-ink-muted)">
                {{ index + 1 }}
              </span>
              <span class="w-[8rem] shrink-0 truncate font-mono text-[11.5px] font-semibold text-(--sk-ink)">
                {{ row.eqp_id }}
              </span>
              <span class="relative h-4 flex-1 overflow-hidden rounded bg-(--sk-border-soft)">
                <span
                  class="absolute inset-y-0 left-0 rounded"
                  :class="tierClass(row.tier)"
                  :style="{ width: `${Math.max(4, Math.round(row.skewPct))}%` }"
                />
              </span>
              <span
                class="w-[3.25rem] shrink-0 text-right font-mono text-[11px] tabular-nums"
                :class="tierTextClass(row.tier)"
                :title="`${row.score.toFixed(3)} nm max-axis skew`"
              >
                {{ row.skewPct.toFixed(0) }}%
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
import type { BeamCondition, RankedTool } from '~/utils/pmPlanning'

export type RankedFocusTool = RankedTool & {
  beam: BeamCondition
  skewPct: number
  tier: 'focus' | 'monitor' | 'ok'
}

const props = defineProps<{
  tools: RankedFocusTool[]
  topN: number
  thresholdPct: number
  selectedToolId: string
}>()

const emit = defineEmits<{
  'update:topN': [value: number]
  'update:thresholdPct': [value: number]
  'select-tool': [toolId: string]
}>()

const topNOptions = ['1', '2', '3', '4', '5', '6', '7', '8']

const beamGroups = computed<BeamCondition[]>(() => {
  const seen = new Set<BeamCondition>()
  for (const tool of props.tools) seen.add(tool.beam)
  return [...seen]
})

const rankedByBeam = computed<Record<string, RankedFocusTool[]>>(() => {
  const groups: Record<string, RankedFocusTool[]> = {}
  for (const beam of beamGroups.value) {
    groups[beam] = props.tools
      .filter(tool => tool.beam === beam)
      .slice(0, props.topN)
  }
  return groups
})

const updateThresholdPct = (value: string | number) => {
  const nextValue = Number(value)
  if (!Number.isFinite(nextValue)) return
  emit('update:thresholdPct', Math.min(100, Math.max(1, nextValue)))
}

const tierClass = (tier: RankedFocusTool['tier']) => {
  if (tier === 'focus') return 'bg-red-500/75'
  if (tier === 'monitor') return 'bg-orange-500/75'
  return 'bg-green-500/70'
}

const tierTextClass = (tier: RankedFocusTool['tier']) => {
  if (tier === 'focus') return 'text-red-600 dark:text-red-400'
  if (tier === 'monitor') return 'text-orange-600 dark:text-orange-400'
  return 'text-green-600 dark:text-green-400'
}
</script>
