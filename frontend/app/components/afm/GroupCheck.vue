<template>
  <label
    class="-m-1.5 flex size-[34px] shrink-0 items-center justify-center rounded-(--sk-r-chip) transition-colors duration-200"
    :class="disabled ? 'cursor-not-allowed' : 'cursor-pointer hover:bg-(--sk-chip-bg)'"
    :title="disabled ? `그룹은 최대 ${AFM_GROUP_MAX}건입니다` : undefined"
  >
    <UCheckbox
      :disabled="disabled"
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
// target, so a row can be picked without aiming. `disabled` is the full group
// refusing one more row.
defineProps<{
  checked: boolean | 'indeterminate'
  label: string
  disabled?: boolean
}>()

defineEmits<{ toggle: [] }>()
</script>
