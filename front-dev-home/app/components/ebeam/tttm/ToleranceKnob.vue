<template>
  <div class="flex items-center gap-3">
    <label class="text-sm text-(--sk-ink-muted)">tolerance</label>
    <input
      type="range"
      :min="range.min"
      :max="range.max"
      :step="range.step"
      :value="modelValue"
      class="accent-(--sk-accent)"
      @input="onInput"
    >
    <span class="tabular-nums text-sm font-medium text-(--sk-ink)">
      {{ modelValue.toFixed(3) }} nm
    </span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: number
  range: { min: number, max: number, step: number }
}>()
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const onInput = (e: Event) => {
  emit('update:modelValue', Number((e.target as HTMLInputElement).value))
}
</script>
