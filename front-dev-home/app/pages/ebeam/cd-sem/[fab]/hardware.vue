<script setup lang="ts">
const { primaryFab } = useFabRoute('cd-sem')
</script>

<template>
  <AppAsyncBoundary title="하드웨어 상태 데이터를 불러오는 중입니다.">
    <EbeamHardwareView
      :fab="primaryFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
