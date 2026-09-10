<template>
  <div class="flex flex-col items-center justify-center gap-2 flex-1 px-6 py-12 text-center">
    <UIcon
      :name="icon"
      class="size-8"
      :class="iconClass"
    />
    <p class="sk-value">
      {{ title }}
    </p>
    <p
      v-if="description"
      class="sk-label"
    >
      {{ description }}
    </p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  iconClass: string
  title: string
  description?: string
}>()
</script>
