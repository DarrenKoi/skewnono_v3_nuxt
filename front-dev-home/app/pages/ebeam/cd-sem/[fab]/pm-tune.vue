<template>
  <!-- 1440px 밀집 예외 (DESIGN.md §Layout): TTTM 과 같은 왼쪽 조작 레일 +
       오른쪽 결과 구성이라 같은 폭을 씁니다. -->
  <div class="mx-auto w-full max-w-[1440px] space-y-3">
    <!-- Keyed on the fab so a fab switch REMOUNTS rather than reusing the view —
         PmTuneView reads props.fab once at setup (both useAsyncData keys bake it
         in), same reasoning as tttm.vue. pm-tune is a SINGLE_FAB_FEATURES page,
         so useFabRoute collapses a multi-fab URL to the primary before this
         renders. -->
    <EbeamPmTuneView
      :key="primaryFab"
      :fab="primaryFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </div>
</template>

<script setup lang="ts">
const { primaryFab } = useFabRoute('cd-sem')
</script>
