<template>
  <UModal
    v-model:open="open"
    :title="`Wafer Map · ${parameter}`"
    :ui="{ content: 'w-[92vw] sm:max-w-[720px]' }"
  >
    <template #body>
      <div class="flex flex-col items-center gap-3">
        <div class="flex w-full items-center justify-end gap-1.5">
          <div class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5">
            <button
              v-for="m in (['Field', 'Die'] as const)"
              :key="m"
              type="button"
              class="rounded-[6px] px-2 py-0.5 font-mono text-[11px] font-medium transition-colors duration-200"
              :class="mode === m ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm' : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="mode = m"
            >
              {{ m }}
            </button>
          </div>
          <EbeamSkewvoirWaferMapOptions
            v-model:options="options"
            :auto-range="autoRange ?? { min: 0, max: 1 }"
          />
        </div>

        <div class="aspect-square w-full max-w-[560px]">
          <EbeamSkewvoirWaferMap
            :rows="rows"
            :parameter="parameter"
            :unit="unit"
            :geo="geo"
            :mode="mode"
            :options="options"
            :color-min="effectiveRange.colorMin"
            :color-max="effectiveRange.colorMax"
            :focused-sequence="focusedSequence"
            :outlier-seqs="outlierSeqs"
            :selected-seqs="selectedSeqs"
            @focus="$emit('focus', $event)"
            @rangechange="autoRange = $event"
          />
        </div>

        <EbeamSkewvoirColorScaleBar
          :min="effectiveRange.colorMin"
          :max="effectiveRange.colorMax"
          :unit="unit"
        />
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { WaferGeometry } from '~/utils/waferGeometry'
import { detailWaferMapOptions, resolveColorRange } from '~/utils/waferMapOptions'

defineProps<{
  rows: MsrFileRow[]
  parameter: string
  unit: string
  geo: WaferGeometry
  focusedSequence: number | null
  outlierSeqs: number[]
  selectedSeqs?: number[]
}>()
defineEmits<{ focus: [sequence: number] }>()

const open = defineModel<boolean>('open', { required: true })

// The modal keeps its own option copy (grid on) so the compact panel is never
// affected by tweaks made here.
const mode = ref<'Field' | 'Die'>('Field')
const options = ref(detailWaferMapOptions())
const autoRange = ref<{ min: number, max: number } | null>(null)
const effectiveRange = computed(() => {
  const auto = autoRange.value ?? { min: 0, max: 1 }
  const r = resolveColorRange(options.value.colorMode, options.value.colorMin, options.value.colorMax, auto)
  return { colorMin: r.min, colorMax: r.max }
})
</script>
