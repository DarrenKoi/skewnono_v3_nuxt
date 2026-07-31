<template>
  <!-- NOT `value-key`. Every other USelectMenu in this repo is `multiple`, where
       `value-key` works; in SINGLE mode it makes Reka's ComboboxItem recompute
       its own selected state on every render, and opening the menu dies with
       “Maximum recursive updates exceeded in <PrimitiveSlot>” (verified in the
       browser 2026-08-01). Binding the item OBJECT and unwrapping `.value` on
       emit keeps the public contract a bare parameter string either way.

       `aria-label` is required as well as `placeholder`: a placeholder only
       renders while nothing is selected, so without it the trigger's accessible
       name stays Reka's default “Show popup”. -->
  <USelectMenu
    :model-value="selectedItem"
    :items="items"
    aria-label="분석 파라미터"
    placeholder="파라미터 선택"
    size="sm"
    class="min-w-64"
    @update:model-value="emit('update:modelValue', $event.value)"
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

// `undefined` (USelectMenu's own "nothing selected" value; it does not accept
// null) when the active parameter is not among the set's options — the trigger
// then falls back to the placeholder rather than showing a stale label.
const selectedItem = computed(() => items.value.find(i => i.value === props.modelValue))
</script>
