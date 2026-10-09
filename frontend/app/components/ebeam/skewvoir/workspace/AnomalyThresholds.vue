<template>
  <section>
    <p class="mb-2 px-1 sk-eyebrow">
      이상 판정 기준
    </p>
    <div class="space-y-2 px-1">
      <USelect
        v-model="draft.method"
        size="sm"
        :items="methodItems"
        class="w-full"
      />
      <div class="flex items-center justify-between gap-1.5">
        <label class="flex items-center gap-1 whitespace-nowrap sk-field-label">
          주의 ±<UInput
            v-model.number="draft.watch"
            type="number"
            min="0"
            size="sm"
            class="w-12"
          />
        </label>
        <label class="flex items-center gap-1 whitespace-nowrap sk-field-label">
          이상 ±<UInput
            v-model.number="draft.abnormal"
            type="number"
            min="0"
            size="sm"
            class="w-12"
          />{{ unit }}
        </label>
      </div>
      <p
        v-if="!valid"
        class="sk-meta"
      >
        주의는 0보다 크고 이상 이하여야 합니다. 이전 기준으로 판정 중입니다.
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { MethodConfig } from '~/utils/anomaly/types'
import { DEFAULT_RANGE, DEFAULT_STDDEV } from '~/utils/anomaly/types'
import { thresholdPair } from '~/utils/skewvoirAnalysis/routeQuery'

// Edits a DRAFT and emits only a valid config: the URL codec reads an invalid
// pair as the defaults, so writing a half-typed value would flip every verdict
// on the screen back to ±10/20% mid-keystroke.
const props = defineProps<{ modelValue: MethodConfig }>()
const emit = defineEmits<{ 'update:modelValue': [MethodConfig] }>()

const methodItems = [
  { label: '범위(%)', value: 'range' },
  { label: '표준편차(σ) · 진단', value: 'stddev' }
]

const draft = reactive({ method: props.modelValue.method, ...thresholdPair(props.modelValue) })
const unit = computed(() => draft.method === 'range' ? '%' : 'σ')
const valid = computed(() => draft.watch > 0 && draft.abnormal >= draft.watch)

// A link or Back/Forward changed the URL under us: follow it.
watch(() => props.modelValue, (cfg) => {
  Object.assign(draft, { method: cfg.method, ...thresholdPair(cfg) })
})

// Switching method shows that method's own thresholds, not the other's numbers
// reinterpreted in a different unit.
watch(() => draft.method, (method) => {
  if (method !== props.modelValue.method) Object.assign(draft, thresholdPair(props.modelValue, method))
})

watch(draft, () => {
  if (!valid.value) return
  const next: MethodConfig = draft.method === 'range'
    ? { method: 'range', range: { ...DEFAULT_RANGE, watchPct: draft.watch, abnormalPct: draft.abnormal }, stddev: { ...DEFAULT_STDDEV } }
    : { method: 'stddev', range: { ...DEFAULT_RANGE }, stddev: { watchK: draft.watch, abnormalK: draft.abnormal } }
  const cur = thresholdPair(props.modelValue)
  if (next.method === props.modelValue.method && cur.watch === draft.watch && cur.abnormal === draft.abnormal) return
  emit('update:modelValue', next)
})
</script>
