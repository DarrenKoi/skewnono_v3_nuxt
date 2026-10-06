<script setup lang="ts">
// The AFM counterpart of NavFeatureTabs: once a tool is chosen (/afm/<tool>/…),
// its four views sit side by side. 측정 결과 owns the search, the detail and
// 시계열 비교; 팁 모니터링, 가동 현황 and Recipe 현황 are one page each, under
// /tips, /usage and /recipes.
const route = useRoute()

const tool = computed(() => {
  const [, section, tool] = route.path.split('/')
  return section === 'afm' && tool ? tool : null
})

const PAGES = [
  { label: '팁 모니터링', icon: 'i-lucide-pen-tool', segment: 'tips' },
  { label: '가동 현황', icon: 'i-lucide-activity', segment: 'usage' },
  { label: 'Recipe 현황', icon: 'i-lucide-list-tree', segment: 'recipes' }
]

const tabs = computed(() => {
  const segment = route.path.split('/')[3]
  return [
    { label: '측정 결과', icon: 'i-lucide-search', to: `/afm/${tool.value}`, active: !PAGES.some(page => page.segment === segment) },
    ...PAGES.map(page => ({ label: page.label, icon: page.icon, to: `/afm/${tool.value}/${page.segment}`, active: page.segment === segment }))
  ]
})
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
