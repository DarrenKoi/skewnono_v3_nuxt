<template>
  <div class="space-y-6">
    <EbeamMetaBar
      eyebrow="AFM"
      title="AFM 장비 선택"
    />
    <UCard class="dashboard-surface">
      <AfmToolList
        tiles
        class="sm:grid sm:grid-cols-3 sm:gap-6 sm:space-y-0"
      />
    </UCard>
  </div>
</template>
