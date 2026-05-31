<template>
  <div
    v-if="tool"
    class="dashboard-surface rounded-2xl px-3.5 py-3"
  >
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <h3 class="text-[12.5px] font-semibold text-(--sk-ink)">
          Convergence drilldown
        </h3>
        <span class="font-mono text-[10.5px] text-(--sk-ink-muted)">
          {{ tool.eqp_id }} / {{ tool.beam }} / rank axis {{ tool.axis }}
        </span>
      </div>
      <span
        class="inline-flex h-6 items-center gap-1 rounded-md px-2 text-[11px] font-semibold"
        :class="tool.tier === 'focus'
          ? 'bg-red-500/15 text-red-600 dark:text-red-400'
          : tool.tier === 'monitor'
            ? 'bg-orange-500/15 text-orange-600 dark:text-orange-400'
            : 'bg-green-500/15 text-green-600 dark:text-green-400'"
      >
        <UIcon
          name="i-lucide-radar"
          class="h-3.5 w-3.5"
        />
        {{ tool.skewPct.toFixed(0) }}% relative skew
      </span>
    </div>

    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <div
        v-for="cell in beamCells"
        :key="`${cell.beam}:${cell.axis}`"
        class="rounded-lg border border-(--sk-border) px-3 py-2"
        :class="cell.axis === tool.axis ? 'bg-(--sk-muted-surface) ring-1 ring-(--sk-accent)' : ''"
      >
        <div class="flex items-center justify-between gap-2">
          <span class="font-mono text-[11px] font-semibold text-(--sk-ink)">
            {{ cell.beam }}.{{ cell.axis }}
          </span>
          <span
            class="inline-flex items-center gap-1 text-[11px] font-semibold"
            :class="Math.abs(cell.gap) >= 0.4 ? 'text-orange-600 dark:text-orange-400' : 'text-(--sk-ink-muted)'"
          >
            <UIcon
              :name="directionIcon(cell.gap)"
              class="h-3.5 w-3.5"
            />
            {{ directionText(cell.gap) }}
          </span>
        </div>

        <dl class="mt-2 grid grid-cols-3 gap-2 font-mono text-[11px] tabular-nums">
          <div>
            <dt class="text-(--sk-ink-muted)">
              current
            </dt>
            <dd class="mt-0.5 font-semibold text-(--sk-ink)">
              {{ cell.current_value.toFixed(3) }}
            </dd>
          </div>
          <div>
            <dt class="text-(--sk-ink-muted)">
              median
            </dt>
            <dd class="mt-0.5 font-semibold text-(--sk-ink)">
              {{ cell.median.toFixed(3) }}
            </dd>
          </div>
          <div>
            <dt class="text-(--sk-ink-muted)">
              signed gap
            </dt>
            <dd
              class="mt-0.5 font-semibold"
              :class="cell.gap >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'"
            >
              {{ cell.gap >= 0 ? '+' : '' }}{{ cell.gap.toFixed(3) }}
            </dd>
          </div>
        </dl>
      </div>
    </div>

    <div class="mt-3">
      <div class="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)">
        <UIcon
          name="i-lucide-history"
          class="h-3.5 w-3.5"
        />
        Epoch history
      </div>

      <div
        v-if="recentEpochs.length"
        class="flex flex-wrap gap-2"
      >
        <div
          v-for="epoch in recentEpochs"
          :key="epoch.epoch_start"
          class="rounded-md bg-(--sk-muted-surface) px-2.5 py-1.5 text-[11px]"
        >
          <span class="font-mono text-(--sk-ink-muted)">{{ epoch.epoch_start }}</span>
          <span class="ml-2 font-mono font-semibold text-(--sk-ink)">MDC {{ epoch.mdc.toFixed(4) }}</span>
          <span class="ml-2 font-mono text-(--sk-ink-muted)">sharp {{ epoch.bsm_sharpness_avg.toFixed(3) }}</span>
        </div>
      </div>

      <p
        v-else
        class="rounded-lg border border-dashed border-(--sk-border) px-3 py-3 text-center text-[11px] text-(--sk-ink-muted)"
      >
        No epoch history is available for the selected tool.
      </p>
    </div>
  </div>

  <div
    v-else
    class="dashboard-surface rounded-2xl px-6 py-8 text-center text-[12px] text-(--sk-ink-muted)"
  >
    Select a ranked tool to inspect its axis convergence and epoch history.
  </div>
</template>

<script setup lang="ts">
import type { EpochPoint } from '~/composables/usePmPlanningApi'
import type { BeamCondition, CellSkew, RankedTool } from '~/utils/pmPlanning'

type ConvergenceTool = RankedTool & {
  beam: BeamCondition
  cells: CellSkew[]
  skewPct: number
  tier: 'focus' | 'monitor' | 'ok'
}

const props = defineProps<{
  tool: ConvergenceTool | null
  epochs: EpochPoint[]
}>()

const beamCells = computed(() =>
  props.tool?.cells.filter(cell => cell.beam === props.tool?.beam) ?? []
)

const recentEpochs = computed(() =>
  props.epochs.slice(-4).reverse()
)

const directionIcon = (gap: number) => {
  if (Math.abs(gap) < 0.05) return 'i-lucide-minus'
  return gap > 0 ? 'i-lucide-arrow-down' : 'i-lucide-arrow-up'
}

const directionText = (gap: number) => {
  if (Math.abs(gap) < 0.05) return 'near median'
  return gap > 0 ? 'reduce' : 'raise'
}
</script>
