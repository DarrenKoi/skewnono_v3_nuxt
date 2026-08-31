<template>
  <!-- 1440px 밀집 예외 (DESIGN.md §Layout): 조작 레일이 상단 비교 대상 바로 바뀐
       뒤에도 폭은 그대로입니다 — 근거가 레일이 아니라 결과 쪽으로 옮겨갔을 뿐입니다.
       2단 카드 쌍이 네 줄이라 1280px 로 좁히면 pairwise 행렬이 1080px 화면 밖으로
       밀립니다. -->
  <div class="mx-auto w-full max-w-[1440px] space-y-3">
    <!-- The one 실험실 analysis page — see utils/labView. PM 플래닝 was a
         second route onto this same component until 2026-09-01; it is now the
         PM 튜닝 chip, and /pm-planning redirects here.

         Keyed on the fab so a fab switch REMOUNTS rather than reusing the view.
         LabView reads props.fab once at setup — both useAsyncData keys bake it
         in, and useTttmSettings resolves the per-fab scope from it — so a reused
         instance would keep serving the previous fab's payload and write the new
         fab's picks into the old fab's saved settings. Nuxt already remounts
         here in practice; the key is what stops that from being an accident this
         page silently depends on. -->
    <EbeamLabView
      :key="primaryFab"
      :fab="primaryFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </div>
</template>

<script setup lang="ts">
// `fabs` is not read: tttm is a SINGLE_FAB_FEATURES page, so useFabRoute slices
// the segment to one and redirects a multi-fab URL to the primary before this
// renders. NavFabScopeNotice ("N개 FAB 중 하나만 표시") therefore never had a
// condition that could be true here, and was dropped with the 2026-08-30 merge.
const { primaryFab } = useFabRoute('cd-sem')
</script>
