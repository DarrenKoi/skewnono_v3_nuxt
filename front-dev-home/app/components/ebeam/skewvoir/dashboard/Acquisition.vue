<template>
  <EbeamSkewvoirPanelFrame
    title="Acquisition"
    :meta="analysis.focusRow.value?.recipe_name ?? '—'"
    icon="i-lucide-settings-2"
  >
    <dl class="grid grid-cols-2 gap-x-4 gap-y-2 px-1 py-1 text-[11.5px]">
      <div
        v-for="field in fields"
        :key="field.label"
        class="flex items-baseline justify-between gap-2 border-b border-(--sk-border-soft) pb-1.5"
      >
        <dt class="text-zinc-400">
          {{ field.label }}
        </dt>
        <dd class="truncate font-mono text-zinc-800 dark:text-zinc-200">
          {{ field.value }}
        </dd>
      </div>
    </dl>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { formatRecipeTimestamp } from '~/utils/recipeView'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const fields = computed(() => {
  const row = props.analysis.focusRow.value
  const file = props.analysis.focusFile.value
  return [
    { label: 'EQ', value: row?.eqp_id ?? '—' },
    { label: 'Vendor', value: row?.vendor_nm ?? '—' },
    { label: 'Model', value: row?.eqp_model_cd ?? '—' },
    { label: 'Class', value: row?.class_name ?? '—' },
    { label: 'Sequences', value: file?.sequence_count != null ? String(file.sequence_count) : '—' },
    { label: 'Images', value: row?.total_images != null ? String(row.total_images) : '—' },
    { label: 'Captured', value: row?.timestamp ? formatRecipeTimestamp(row.timestamp) : '—' },
    { label: 'MeasTime', value: row?.meastime != null ? `${row.meastime}s` : '—' }
  ]
})
</script>
