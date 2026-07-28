<template>
  <div class="grid min-h-0 grid-cols-1 gap-x-6 overflow-auto sm:grid-cols-2">
    <div :class="rowClass">
      <span :class="labelClass">Parameter</span>
      <span :class="[valueClass, 'font-mono']">{{ row.Parameter }}</span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">Region</span>
      <span :class="[valueClass, 'font-mono']">{{ row.Region }}</span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">SEQ</span>
      <span :class="[valueClass, 'font-mono']">{{ row.SEQ }} / {{ row.Last_SEQ }}</span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">Mother_Para</span>
      <span :class="valueClass">
        <EbeamRecipeOpenBoolPill :value="row.Mother_Para" />
      </span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">Addressing</span>
      <span :class="valueClass">
        <EbeamRecipeOpenBoolPill :value="row.Addressing" />
      </span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">Double_Addressing</span>
      <span :class="valueClass">
        <EbeamRecipeOpenBoolPill :value="row.Double_Addressing" />
      </span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">Meas_Counting</span>
      <span :class="[valueClass, 'font-mono']">{{ row.Meas_Counting }}</span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">dnumber_removed</span>
      <span :class="valueClass">
        <EbeamRecipeOpenBoolPill
          :value="row.dnumber_removed"
          :ok-when="false"
        />
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'

defineProps<{
  row: IdpImageInfoRow
}>()

const rowClass = 'flex items-baseline justify-between gap-3 border-b border-zinc-100 py-1.5 dark:border-zinc-800/60'
const labelClass = 'sk-label'
const valueClass = 'text-right sk-value'
</script>
