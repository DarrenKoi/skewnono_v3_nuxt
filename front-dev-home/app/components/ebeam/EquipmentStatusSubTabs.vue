<template>
  <!-- These sub-tabs change the route, so by the BLACK/TERRACOTTA litmus test
       they are NAVIGATE and take sk-nav-pill (ink fill), not a chip and not a
       hand-rolled segmented control. SkNavPill emits aria-current="page" when
       given `to`, which is the correct semantic for a link that owns the view. -->
  <nav
    aria-label="장비 상태 sub-view"
    class="inline-flex items-center gap-1"
  >
    <SkNavPill
      v-for="option in options"
      :key="option.value"
      :to="option.to"
      :icon="option.icon"
      :label="option.label"
      :active="active === option.value"
      size="sm"
    />
  </nav>
</template>

<script setup lang="ts">
const SUB_TABS = [
  { value: 'list', label: '장비 리스트', icon: 'i-lucide-server' },
  { value: 'storage', label: '스토리지', icon: 'i-lucide-hard-drive' }
] as const

type SubTabValue = typeof SUB_TABS[number]['value']

const route = useRoute()

const isStorage = computed(() => route.path.includes('/storage'))
const basePath = computed(() => isStorage.value ? route.path.replace(/\/storage(\/.*)?$/, '') : route.path)
const active = computed<SubTabValue>(() => isStorage.value ? 'storage' : 'list')

const options = computed(() =>
  SUB_TABS.map(tab => ({
    ...tab,
    to: tab.value === 'storage' ? `${basePath.value}/storage` : basePath.value
  }))
)
</script>
