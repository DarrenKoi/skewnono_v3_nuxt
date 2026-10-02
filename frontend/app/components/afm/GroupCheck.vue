<template>
  <label class="-m-1.5 flex size-[34px] shrink-0 cursor-pointer items-center justify-center rounded-(--sk-r-chip) transition-colors duration-200 hover:bg-(--sk-chip-bg)">
    <UCheckbox
      size="xl"
      :ui="{ base: 'ring-(--sk-ink-subtle)' }"
      :model-value="checked"
      :aria-label="label"
      @update:model-value="$emit('toggle')"
    />
  </label>
</template>

<script setup lang="ts">
// The "담기" checkbox of the AFM measurement lists: a 20px box inside a 34px
// target, so a row can be picked without aiming.
defineProps<{
  checked: boolean | 'indeterminate'
  label: string
}>()

defineEmits<{ toggle: [] }>()
</script>
