<template>
  <div class="max-w-5xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <EbeamMetaBar
      eyebrow="AFM"
      title="AFM 장비 선택"
    />
    <UCard class="dashboard-surface">
      <AfmToolList />
    </UCard>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})
</script>
