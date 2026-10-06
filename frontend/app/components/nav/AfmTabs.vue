<script setup lang="ts">
// The AFM counterpart of NavFeatureTabs: once a tool is chosen (/afm/<tool>/…),
// its two worlds sit side by side. 측정 결과 owns the search, the detail and
// 시계열 비교; 팁 모니터링 is the one page under /tips.
const route = useRoute()

const tool = computed(() => {
  const [, section, tool] = route.path.split('/')
  return section === 'afm' && tool ? tool : null
})
const onTips = computed(() => route.path.split('/')[3] === 'tips')

const tabs = computed(() => [
  { label: '측정 결과', icon: 'i-lucide-search', to: `/afm/${tool.value}`, active: !onTips.value },
  { label: '팁 모니터링', icon: 'i-lucide-pen-tool', to: `/afm/${tool.value}/tips`, active: onTips.value }
])
</script>

<template>
  <nav
    v-if="tool"
    aria-label="AFM navigation"
    class="flex gap-1 min-w-0 overflow-x-auto"
  >
    <SkNavPill
      v-for="tab in tabs"
      :key="tab.label"
      :label="tab.label"
      :aria-label="tab.label"
      :icon="tab.icon"
      :active="tab.active"
      :to="tab.to"
      size="sm"
      label-class="hidden lg:inline"
      :class="tab.active ? 'shadow-sm sk-nav-accent' : undefined"
    />
  </nav>
</template>
