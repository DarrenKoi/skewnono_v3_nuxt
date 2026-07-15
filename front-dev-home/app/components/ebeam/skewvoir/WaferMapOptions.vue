<template>
  <UPopover :content="{ align: 'end' }">
    <UButton
      icon="i-lucide-settings-2"
      color="neutral"
      variant="ghost"
      size="xs"
      aria-label="표시 옵션"
    />
    <template #content>
      <div class="w-56 space-y-2.5 p-3">
        <p class="sk-label">
          표시 옵션
        </p>
        <div class="space-y-1.5">
          <UCheckbox
            v-model="model.crosshair"
            label="중심선 (crosshair)"
            size="xs"
          />
          <UCheckbox
            v-model="model.grid"
            label="격자 · Die 번호"
            size="xs"
          />
          <UCheckbox
            v-model="model.mpLabels"
            label="MP 번호 표시"
            size="xs"
          />
          <UCheckbox
            v-model="model.notch"
            label="Notch 표시"
            size="xs"
          />
        </div>

        <div class="border-t border-(--sk-border-soft) pt-2.5">
          <p class="sk-label mb-1.5">
            색상 범위
          </p>
          <div class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5">
            <button
              v-for="m in colorModes"
              :key="m.value"
              type="button"
              class="rounded-[6px] px-2 py-0.5 font-mono text-[11px] font-medium transition-colors duration-200"
              :class="model.colorMode === m.value
                ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
                : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="setColorMode(m.value)"
            >
              {{ m.label }}
            </button>
          </div>
          <div
            v-if="model.colorMode === 'manual'"
            class="mt-2 flex items-center gap-1.5"
          >
            <UInput
              v-model.number="model.colorMin"
              type="number"
              size="xs"
              placeholder="min"
              class="w-full"
            />
            <span class="text-(--sk-ink-subtle)">–</span>
            <UInput
              v-model.number="model.colorMax"
              type="number"
              size="xs"
              placeholder="max"
              class="w-full"
            />
          </div>
        </div>
      </div>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import type { WaferMapOptions } from '~/utils/waferMapOptions'

// v-model:options — the parent owns the option object; this popover mutates it.
const model = defineModel<WaferMapOptions>('options', { required: true })

// The current auto (data) color range, so switching to Manual can seed real
// numbers into the inputs instead of leaving them blank.
const props = defineProps<{ autoRange: { min: number, max: number } }>()

const colorModes = [
  { value: 'auto' as const, label: 'Auto' },
  { value: 'manual' as const, label: 'Manual' }
]

const setColorMode = (mode: 'auto' | 'manual') => {
  model.value.colorMode = mode
  if (mode === 'manual' && (model.value.colorMin == null || model.value.colorMax == null)) {
    model.value.colorMin = Number(props.autoRange.min.toFixed(1))
    model.value.colorMax = Number(props.autoRange.max.toFixed(1))
  }
}
</script>
