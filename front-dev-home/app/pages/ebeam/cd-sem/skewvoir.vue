<template>
  <EbeamComingSoon
    eyebrow="CD-SEM"
    title="스큐보아"
    subtitle="AI 기반 장비 인사이트 (Skewvoir)"
    :fab="fabId"
    icon="i-lucide-eye"
  />
</template>

<script setup lang="ts">
definePageMeta({
  hideFabSidebar: true
})

const { setToolType, fab } = useNavigation()

const fabId = computed(() => (fab.value && fab.value !== 'all' ? fab.value : '').toUpperCase())

setToolType('cd-sem')
</script>
