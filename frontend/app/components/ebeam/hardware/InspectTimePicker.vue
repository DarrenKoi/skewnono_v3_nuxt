<template>
  <!-- The keyboard path to the recipe window: pick a time, press the button.
       Charts reach the same popup from their tooltip. -->
  <div class="flex items-center gap-2">
    <USelect
      v-model="model"
      :items="items"
      size="xs"
      icon="i-lucide-clock"
      :placeholder="placeholder"
      :class="selectClass"
      :aria-label="label"
    />
    <UButton
      v-if="model"
      size="xs"
      color="neutral"
      variant="outline"
      icon="i-lucide-file-search"
      label="이 시점 측정 recipe"
      @click="emit('inspect', model)"
    />
  </div>
</template>

<script setup lang="ts">
// Offset-less KST wall clock of the picked time.
const model = defineModel<string>({ required: true })
defineProps<{
  items: (string | { value: string, label: string })[]
  label: string
  selectClass?: string
  placeholder?: string
}>()
const emit = defineEmits<{ inspect: [at: string] }>()
</script>
