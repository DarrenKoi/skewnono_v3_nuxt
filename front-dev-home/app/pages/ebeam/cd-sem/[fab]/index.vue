<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('cd-sem')
</script>

<template>
  <div class="h-full">
    <AppAsyncBoundary title="장비 리스트를 불러오는 중입니다.">
      <EbeamToolInventoryView
        tool-type="cd-sem"
        :fab="primaryFab"
        :eyebrow="`CD-SEM · ${fabs.join(' + ')}`"
        title="장비 상태"
        subtitle="스큐노노가 현재 접근 가능한 장비 리스트입니다."
        cadence="1시간 주기"
      />
    </AppAsyncBoundary>
  </div>
</template>
