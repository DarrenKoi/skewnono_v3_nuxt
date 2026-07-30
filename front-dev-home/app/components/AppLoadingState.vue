<template>
  <div
    class="dashboard-surface rounded-2xl px-6 py-12"
    role="status"
    aria-live="polite"
  >
    <div class="mx-auto max-w-md">
      <UProgress
        animation="carousel"
        size="sm"
      />
      <p class="mt-4 text-center sk-body">
        {{ title }}
      </p>
      <p
        v-if="description"
        class="mt-1 text-center sk-meta"
      >
        {{ description }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>
