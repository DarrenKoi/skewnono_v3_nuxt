<script setup lang="ts">
const { ownerFab } = useRecipeDetailRouting('cd-sem')
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-3">
    <AppAsyncBoundary title="Recipe 내용을 불러오는 중입니다.">
      <EbeamRecipeOpenView
        :fab="ownerFab"
        tool-label="CD-SEM"
        tool-type="cd-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
