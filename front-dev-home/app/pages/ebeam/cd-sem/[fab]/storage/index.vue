<script setup lang="ts">
const { fabs } = useFabRoute('cd-sem')
</script>

<template>
  <div class="space-y-3">
    <AppAsyncBoundary title="스토리지 정보를 불러오는 중입니다.">
      <EbeamStorageView
        :fabs="fabs"
        tool-label="CD-SEM"
        tool-type="cd-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
