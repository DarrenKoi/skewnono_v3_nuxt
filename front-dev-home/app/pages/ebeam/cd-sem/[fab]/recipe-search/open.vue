<script setup lang="ts">
import { readRecipeOwnerFabQuery } from '~/utils/recipeView'

const { primaryFab } = useFabRoute('cd-sem')
const route = useRoute()
const ownerFab = computed(() => readRecipeOwnerFabQuery(route) || primaryFab.value)
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
