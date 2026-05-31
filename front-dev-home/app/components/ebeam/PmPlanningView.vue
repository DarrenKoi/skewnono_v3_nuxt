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

    <div
      v-else-if="tools.length"
      class="dashboard-surface rounded-2xl px-4 py-3 text-xs text-(--sk-ink-muted)"
    >
      Focus controls staged:
      N={{ focusN }},
      <span
        v-for="beam in beamConditions"
        :key="beam"
        class="ml-2 font-mono"
      >
        {{ beam }} {{ (threshold[beam] ?? 0).toFixed(2) }}nm
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { usePmPlanningApi, type FleetResponse, type ToolBlock } from '~/composables/usePmPlanningApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import type { BeamCondition } from '~/utils/pmPlanning'

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

const focusN = ref(3)
const threshold = ref<Record<string, number>>({ '500V': 0.30, '800V': 0.40 })
const beamConditions = computed<BeamCondition[]>(() => fleet.value?.beam_conditions ?? ['500V', '800V'])

watch(fleet, (nextFleet) => {
  if (!nextFleet) return
  focusN.value = nextFleet.defaults.focus_n
  threshold.value = { ...nextFleet.defaults.advisory_threshold }
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
