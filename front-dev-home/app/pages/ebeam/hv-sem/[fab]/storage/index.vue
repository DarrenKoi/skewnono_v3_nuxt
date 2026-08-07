<script setup lang="ts">
const { fabs } = useFabRoute('hv-sem')
</script>

<template>
  <div class="space-y-3">
    <AppAsyncBoundary title="스토리지 정보를 불러오는 중입니다.">
      <EbeamStorageView
        :fabs="fabs"
        tool-label="HV-SEM"
        tool-type="hv-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
