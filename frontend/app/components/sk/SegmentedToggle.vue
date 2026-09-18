<template>
  <!-- Chip-style segmented control (the PanelFrame header toggle, as a
       standalone). Items may be disabled with a reason shown on hover. -->
  <div
    class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
    role="group"
    :aria-label="label"
  >
    <button
      v-for="item in items"
      :key="String(item.value)"
      type="button"
      class="rounded-[6px] px-2.5 py-1 font-mono text-xs font-medium transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40"
      :class="item.value === modelValue
        ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
        : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
      :aria-pressed="item.value === modelValue"
      :disabled="item.disabled"
      :title="item.disabled ? item.disabledReason : undefined"
      @click="emit('update:modelValue', item.value)"
    >
      {{ item.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  items: { label: string, value: string, disabled?: boolean, disabledReason?: string }[]
  modelValue: string
  /** Group name for assistive tech, e.g. 추세 모델. */
  label: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
