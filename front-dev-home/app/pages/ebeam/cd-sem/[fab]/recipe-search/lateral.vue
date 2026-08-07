<script setup lang="ts">
import { readRecipeOwnerFabQuery } from '~/utils/recipeView'

const { primaryFab } = useFabRoute('cd-sem')
const route = useRoute()
const ownerFab = computed(() => readRecipeOwnerFabQuery(route) || primaryFab.value)
</script>

<template>
  <AppAsyncBoundary title="Recipe 횡전개 정보를 불러오는 중입니다.">
    <EbeamRecipeLateralView
      :fab="ownerFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
