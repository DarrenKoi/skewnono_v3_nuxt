<script setup lang="ts">
const { fabs } = useFabRoute('hv-sem')
</script>

<template>
  <AppAsyncBoundary title="하드웨어 상태 데이터를 불러오는 중입니다.">
    <EbeamHardwareView
      :fabs="fabs"
      tool-label="HV-SEM"
      tool-type="hv-sem"
    />
  </AppAsyncBoundary>
</template>
