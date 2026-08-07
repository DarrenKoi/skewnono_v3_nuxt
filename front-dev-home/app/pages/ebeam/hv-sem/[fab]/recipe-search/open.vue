<script setup lang="ts">
const { ownerFab } = useRecipeDetailRouting('hv-sem')
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-3">
    <AppAsyncBoundary title="Recipe 내용을 불러오는 중입니다.">
      <EbeamRecipeOpenView
        :fab="ownerFab"
        tool-label="HV-SEM"
        tool-type="hv-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
