<template>
  <USelectMenu
    :model-value="selected"
    :items="items"
    value-key="value"
    placeholder="파라미터 선택"
    size="sm"
    class="min-w-64"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<script setup lang="ts">
import type { SetParamOption } from '~/utils/skewvoirAnalysis/timeSeries'
import { paramLabel } from '~/utils/skewvoirAnalysis/paramOrder'

const props = defineProps<{
  options: SetParamOption[]
  modelValue: string
}>()

const emit = defineEmits<{ 'update:modelValue': [parameter: string] }>()

// Coverage is shown on every option so a silent drop becomes a visible one:
// picking a parameter 22 of 30 measurements carry should look different from
// picking one they all share.
const items = computed(() => props.options.map(o => ({
  label: `${paramLabel(o.parameter)} · ${o.covered}/${o.loaded}`,
  value: o.parameter
})))

const selected = computed(() => props.modelValue)
</script>
