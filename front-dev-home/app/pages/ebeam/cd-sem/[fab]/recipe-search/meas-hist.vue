<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('cd-sem')
</script>

<template>
  <div class="space-y-3">
    <FabScopeNotice
      :fabs="fabs"
      :primary-fab="primaryFab"
    />
    <AppAsyncBoundary title="측정 이력을 불러오는 중입니다.">
      <EbeamRecipeMeasHistView
        :fab="primaryFab"
        tool-label="CD-SEM"
        tool-type="cd-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
