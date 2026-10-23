<script setup lang="ts">
const { fabs } = useFabRoute('veritysem')
</script>

<template>
  <div class="h-full">
    <AppAsyncBoundary title="장비 리스트를 불러오는 중입니다.">
      <EbeamToolInventoryView
        tool-type="veritysem"
        :fabs="fabs"
        :eyebrow="`VeritySEM · ${fabs.join(' + ')}`"
        title="장비 상태"
        subtitle="스큐노노가 현재 접근 가능한 장비 리스트입니다."
      />
    </AppAsyncBoundary>
  </div>
</template>
