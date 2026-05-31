<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="identity"
      title="PM Planning"
      subtitle="BM/PM Up gate and next-PM focus targets."
      :as-of="fleet?.anchor_date"
      cadence="Daily"
      :stats="metaStats"
    />

    <EbeamPmPlanningGateStrip
      :tools="tools"
      :selected-eqp-id="selectedEqpId"
      @update:selected-eqp-id="selectedEqpId = $event"
    />

    <div
      v-if="status === 'pending' && !tools.length"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="mx-auto h-5 w-5 animate-spin text-zinc-400"
      />
      <p class="mt-2">
        Loading fleet skew snapshot...
      </p>
    </div>

    <div
      v-else-if="error"
      class="dashboard-surface rounded-2xl px-6 py-6 text-sm text-red-600 dark:text-red-400"
    >
      PM Planning fleet request failed: {{ error.message }}
    </div>

    <EbeamPmPlanningFocusRanking
      v-else-if="tools.length"
      v-model:top-n="topN"
      v-model:threshold-pct="thresholdPct"
      :tools="rankedTools"
      :selected-tool-id="selectedToolId"
      @select-tool="selectedToolId = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { usePmPlanningApi, type FleetResponse, type ToolBlock } from '~/composables/usePmPlanningApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { rankFocusTargets, type BeamCondition, type RankedTool } from '~/utils/pmPlanning'

type RankedFocusTool = RankedTool & {
  beam: BeamCondition
  skewPct: number
  tier: 'focus' | 'monitor' | 'ok'
}

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: 'cd-sem'
}>()

const identity = computed(() => `${props.toolLabel} - ${props.fab || '-'}`)

const { fetchPmPlanningFleet } = usePmPlanningApi()

const cacheKey = computed(() => `pm-planning:${props.fab || 'NONE'}`)

const { data: fleet, status, error } = await useAsyncData<FleetResponse | null>(
  () => cacheKey.value,
  () => props.fab ? fetchPmPlanningFleet(props.fab) : Promise.resolve(null),
  { watch: [cacheKey] }
)

const tools = computed<ToolBlock[]>(() => fleet.value?.tools ?? [])

const selectedEqpId = ref<string | null>(null)

watch(tools, (list) => {
  if (selectedEqpId.value && list.some(tool => tool.eqp_id === selectedEqpId.value)) return
  const hold = list.find(tool => tool.gate.verdict === 'hold')
  selectedEqpId.value = hold?.eqp_id ?? list[0]?.eqp_id ?? null
}, { immediate: true })

const topN = ref(5)
const thresholdPct = ref(80)
const selectedToolId = ref('')
const beamConditions = computed<BeamCondition[]>(() => fleet.value?.beam_conditions ?? ['500V', '800V'])

const rankedTools = computed<RankedFocusTool[]>(() => {
  const rows: RankedFocusTool[] = []

  for (const beam of beamConditions.value) {
    const ranked = rankFocusTargets(tools.value, beam, 0, tools.value.length)
    const maxScore = ranked[0]?.score ?? 0

    rows.push(...ranked.slice(0, topN.value).map((tool: RankedTool) => {
      const skewPct = maxScore > 0 ? (tool.score / maxScore) * 100 : 0
      const tier: RankedFocusTool['tier'] = skewPct >= thresholdPct.value
        ? 'focus'
        : skewPct >= thresholdPct.value * 0.75
          ? 'monitor'
          : 'ok'

      return {
        ...tool,
        beam,
        skewPct,
        tier
      }
    }))
  }

  return rows
})

const metaStats = computed<MetaBarStat[]>(() => {
  const list = tools.value
  const upCount = list.filter(tool => tool.gate.verdict === 'up').length
  const holdCount = list.length - upCount

  return [
    { key: 'fleet', label: 'Fleet tools', value: String(list.length), tone: 'neutral' },
    { key: 'up', label: 'Up ready', value: String(upCount), tone: 'ok' },
    { key: 'hold', label: 'Hold', value: String(holdCount), tone: holdCount ? 'warn' : 'neutral' }
  ]
})
</script>
