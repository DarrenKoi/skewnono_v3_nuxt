<template>
  <!-- 1440px 밀집 예외 (DESIGN.md §Layout): 장비간 스큐 화면과 같은 상단 바 +
       아래 결과 구성이라 같은 폭을 씁니다. -->
  <div class="mx-auto w-full max-w-[1440px] space-y-3">
    <!-- The PM 플래닝 view of the same component /tttm renders — see
         utils/labView for why both routes survived the merge. Keyed on the fab
         for the reason tttm.vue is. -->
    <EbeamLabView
      :key="primaryFab"
      :fab="primaryFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
      view="pm-planning"
    />
  </div>
</template>

<script setup lang="ts">
const { primaryFab } = useFabRoute('cd-sem')
</script>
