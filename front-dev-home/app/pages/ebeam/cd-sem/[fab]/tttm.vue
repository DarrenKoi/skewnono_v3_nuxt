<template>
  <!-- 1440px 밀집 예외 (DESIGN.md §Layout): 왼쪽 392px 조작 레일 + 오른쪽 결과라는
       리스트-플러스-상세 성격이라 Mag/Pixel 가이드와 같은 폭을 씁니다. -->
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
