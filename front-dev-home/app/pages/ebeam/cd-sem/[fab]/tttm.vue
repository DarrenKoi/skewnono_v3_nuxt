<template>
  <!-- 1440px 밀집 예외 (DESIGN.md §Layout): 조작 레일이 상단 비교 대상 바로 바뀐
       뒤에도 폭은 그대로입니다 — 근거가 레일이 아니라 결과 쪽으로 옮겨갔을 뿐입니다.
       2단 카드 쌍이 네 줄이라 1280px 로 좁히면 pairwise 행렬이 1080px 화면 밖으로
       밀립니다. -->
  <div class="mx-auto w-full max-w-[1440px] space-y-3">
    <NavFabScopeNotice
      :fabs="fabs"
      :primary-fab="primaryFab"
    />
    <!-- Keyed on the fab so a fab switch REMOUNTS rather than reusing the view.
         TttmView reads props.fab once at setup — useTttmCheck bakes it into the
         useAsyncData key, and useTttmSettings resolves the per-fab scope from
         it — so a reused instance would keep serving the previous fab's payload
         and write the new fab's picks into the old fab's saved settings. Nuxt
         already remounts here in practice; the key is what stops that from
         being an accident this page silently depends on. -->
    <EbeamTttmView
      :key="primaryFab"
      :fab="primaryFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </div>
</template>

<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('cd-sem')
</script>
