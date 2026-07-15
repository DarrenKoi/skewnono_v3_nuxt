<template>
  <div class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="flex flex-wrap items-center gap-x-5 gap-y-3">
      <div class="flex items-center gap-2">
        <span class="font-mono text-[10px] text-(--sk-ink-muted)">Tool</span>
        <USelect
          :model-value="selectedEqpId ?? undefined"
          :items="toolOptions"
          size="sm"
          class="w-[13rem]"
          @update:model-value="(value: string) => emit('update:selectedEqpId', value)"
        />
      </div>

      <template v-if="gate">
        <span
          class="inline-flex h-7 items-center gap-1.5 rounded-md px-3 text-sm font-semibold"
          :class="gate.verdict === 'up'
            ? 'bg-green-500/15 text-green-600 dark:text-green-400'
            : 'bg-red-500/15 text-red-600 dark:text-red-400'"
        >
          <UIcon
            :name="gate.verdict === 'up' ? 'i-lucide-circle-check' : 'i-lucide-circle-slash'"
            class="h-4 w-4"
          />
          {{ gate.verdict === 'up' ? 'Up ready' : 'Hold' }}
        </span>

        <div class="flex items-center gap-2">
          <span
            class="inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium ring-1"
            :class="conditionClass(gate.cd_in_spec)"
            :title="`spec [${gate.cd_spec_lower}, ${gate.cd_spec_upper}] nm`"
          >
            <UIcon
              :name="gate.cd_in_spec ? 'i-lucide-check' : 'i-lucide-x'"
              class="h-3.5 w-3.5"
            />
            CD_MON {{ gate.cd_monitoring_value.toFixed(2) }}
          </span>
          <span
            class="inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium ring-1"
            :class="conditionClass(gate.bsm_in_spec)"
            :title="`sharpness ${gate.bsm_sharpness_avg}, noise ${gate.bsm_noise_avg}`"
          >
            <UIcon
              :name="gate.bsm_in_spec ? 'i-lucide-check' : 'i-lucide-x'"
              class="h-3.5 w-3.5"
            />
            BSM
          </span>
        </div>

        <div class="flex items-center gap-2 sk-meta">
          <span
            class="inline-flex h-6 items-center gap-1 rounded px-2"
            :class="advisory.beyond ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400' : ''"
          >
            <UIcon
              name="i-lucide-radar"
              class="h-3.5 w-3.5"
            />
            advisory {{ advisory.score.toFixed(2) }}nm ({{ advisory.beam }}.{{ advisory.axis }})
            <template v-if="advisory.beyond">
              next PM candidate
            </template>
          </span>
          <span
            v-if="gate.prev_post_delta !== null"
            class="font-mono"
            title="Before/after delta; context only."
          >
            delta {{ gate.prev_post_delta >= 0 ? '+' : '' }}{{ gate.prev_post_delta.toFixed(2) }}
          </span>
          <span
            v-if="gate.mdc_changed"
            class="inline-flex h-6 items-center gap-1 rounded bg-zinc-500/10 px-2"
            title="MDC changed in this epoch; context only."
          >
            <UIcon
              name="i-lucide-git-commit-horizontal"
              class="h-3.5 w-3.5"
            />
            MDC changed
          </span>
        </div>
      </template>

      <span
        v-else
        class="sk-body"
      >
        No tools in this fleet snapshot.
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ToolBlock } from '~/composables/usePmPlanningApi'
import { maxAxisSkew, type BeamCondition, type ScanAxis } from '~/utils/pmPlanning'

const props = defineProps<{
  tools: ToolBlock[]
  selectedEqpId: string | null
}>()

const emit = defineEmits<{
  'update:selectedEqpId': [value: string]
}>()

const toolOptions = computed(() =>
  props.tools.map(tool => ({
    label: `${tool.eqp_id}${tool.gate.verdict === 'hold' ? ' - Hold' : ''}`,
    value: tool.eqp_id
  }))
)

const selectedTool = computed(() =>
  props.tools.find(tool => tool.eqp_id === props.selectedEqpId) ?? null
)

const gate = computed(() => selectedTool.value?.gate ?? null)

const conditionClass = (ok: boolean) =>
  ok
    ? 'bg-green-500/10 text-green-600 ring-green-500/30 dark:text-green-400'
    : 'bg-red-500/10 text-red-600 ring-red-500/30 dark:text-red-400'

const advisoryDefaults: Record<BeamCondition, number> = { '500V': 0.30, '800V': 0.40 }

const advisory = computed(() => {
  const tool = selectedTool.value
  if (!tool) return { score: 0, beam: '500V' as BeamCondition, axis: 'X' as ScanAxis, beyond: false }

  let worst = { score: 0, beam: '500V' as BeamCondition, axis: 'X' as ScanAxis, beyond: false }
  for (const beam of ['500V', '800V'] as BeamCondition[]) {
    const { score, axis } = maxAxisSkew(tool.cells, beam)
    if (score >= worst.score) {
      worst = { score, beam, axis, beyond: score > advisoryDefaults[beam] }
    }
  }

  return worst
})
</script>
