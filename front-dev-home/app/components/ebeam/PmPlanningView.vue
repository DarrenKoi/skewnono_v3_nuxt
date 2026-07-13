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
        class="mx-auto h-5 w-5 animate-spin text-(--sk-ink-muted)"
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

    <template v-else-if="tools.length">
      <EbeamPmPlanningFocusRanking
        :tools="tools"
        :beam-conditions="beamConditions"
        :focus-n="focusN"
        :threshold="threshold"
        :selected="focusSelection"
        @update:focus-n="focusN = $event"
        @update:threshold="setThreshold"
        @select="selectFocus"
      />

      <EbeamPmPlanningConvergencePanel
        :tools="tools"
        :selection="focusSelection"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { usePmPlanningApi, type FleetResponse, type ToolBlock } from '~/composables/usePmPlanningApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { rankFocusTargets, type BeamCondition } from '~/utils/pmPlanning'

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

// Focus-ranking knobs — seeded from the server defaults, then engineer-tunable
// (client-only). The per-beam threshold is in nm and acts as the self-limiting
// gate inside rankFocusTargets; raising it nominates fewer tools.
const beamConditions = computed<BeamCondition[]>(() => fleet.value?.beam_conditions ?? ['500V', '800V'])
const focusN = ref(3)
const threshold = ref<Record<string, number>>({ '500V': 0.30, '800V': 0.40 })

watch(fleet, (snapshot) => {
  if (!snapshot) return
  focusN.value = snapshot.defaults.focus_n
  threshold.value = { ...snapshot.defaults.advisory_threshold }
}, { immediate: true })

const setThreshold = ({ beam, value }: { beam: BeamCondition, value: number }) => {
  threshold.value = { ...threshold.value, [beam]: value }
}

// Selected (beam, tool) for the convergence panel. Auto-selects the worst
// nominee of the first beam that still has one, so the panel isn't empty on
// load and re-resolves when the knobs change the candidate set.
const focusSelection = ref<{ beam: BeamCondition, eqpId: string } | null>(null)

const selectFocus = (payload: { beam: BeamCondition, eqpId: string }) => {
  focusSelection.value = payload
}

watch([tools, beamConditions, focusN, threshold], () => {
  const current = focusSelection.value
  if (current) {
    const stillRanked = rankFocusTargets(tools.value, current.beam, threshold.value[current.beam] ?? 0, focusN.value)
      .some(row => row.eqp_id === current.eqpId)
    if (stillRanked) return
  }
  for (const beam of beamConditions.value) {
    const top = rankFocusTargets(tools.value, beam, threshold.value[beam] ?? 0, focusN.value)[0]
    if (top) {
      focusSelection.value = { beam, eqpId: top.eqp_id }
      return
    }
  }
  focusSelection.value = null
}, { immediate: true })

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
