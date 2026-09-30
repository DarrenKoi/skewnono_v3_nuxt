<template>
  <!-- One row of NAVIGATE pills (DESIGN.md: BLACK = navigate) joined into a
       single bordered control, for a view switch inside a panel. -->
  <div
    role="tablist"
    :aria-label="label"
    class="flex w-fit overflow-hidden rounded-[var(--sk-r-nav)] border border-(--sk-border)"
  >
    <SkNavPill
      v-for="item in items"
      :key="item.value"
      role="tab"
      :aria-selected="item.value === modelValue"
      :active="item.value === modelValue"
      :label="item.label"
      :count="item.count"
      size="sm"
      class="!rounded-none !border-0"
      @click="emit('update:modelValue', item.value)"
    />
  </div>
</template>

<script setup lang="ts" generic="T extends string">
defineProps<{
  items: readonly { value: T, label: string, count?: number }[]
  modelValue: T
  /** Group name for assistive tech, e.g. FDC 보기. */
  label: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
</script>
