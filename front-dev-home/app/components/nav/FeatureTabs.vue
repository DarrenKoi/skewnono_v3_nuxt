<script setup lang="ts">
import type { ToolType } from '~/stores/navigation'

const route = useRoute()

type FeatureRouteValue = 'index' | 'storage' | 'recipe-search' | 'device-statistics'

type FeatureTab = {
  label: string
  icon: string
  badgeIcon?: string
  routeValue?: FeatureRouteValue
  enabledToolTypes?: ToolType[]
}

const features: FeatureTab[] = [
  { label: '장비 리스트', routeValue: 'index', icon: 'i-lucide-layout-dashboard', enabledToolTypes: ['cd-sem', 'hv-sem'] },
  { label: '스토리지', routeValue: 'storage', icon: 'i-lucide-database', enabledToolTypes: ['cd-sem', 'hv-sem'] },
  { label: 'Recipe 검색', routeValue: 'recipe-search', icon: 'i-lucide-search', enabledToolTypes: ['cd-sem', 'hv-sem'] },
  { label: '디바이스 통계', routeValue: 'device-statistics', icon: 'i-lucide-bar-chart-3', enabledToolTypes: ['cd-sem'] },
  { label: 'Fail 이슈', icon: 'i-lucide-triangle-alert' },
  { label: 'H/W 관리', icon: 'i-lucide-cpu' },
  { label: '스큐보아', icon: 'i-lucide-eye', badgeIcon: 'i-lucide-sparkles' }
]

const toolTypes: ToolType[] = ['cd-sem', 'hv-sem', 'verity-sem', 'provision']

const routeToolType = computed<ToolType | null>(() => {
  const [, category, toolType] = route.path.split('/')
  if (category !== 'ebeam') return null
  return toolTypes.includes(toolType as ToolType) ? toolType as ToolType : null
})

const activeFeature = computed(() => {
  const path = route.path
  if (path.includes('/storage')) return 'storage'
  if (path.includes('/recipe-search')) return 'recipe-search'
  if (path.includes('/device-statistics')) return 'device-statistics'
  return 'index'
})

const getFeatureRoute = (feature: string) => {
  const basePath = route.path.replace(/\/(storage|recipe-search|device-statistics)$/, '')
  if (feature === 'index') return basePath
  return `${basePath}/${feature}`
}

const isFeatureEnabled = (feature: FeatureTab) => {
  if (!feature.routeValue) return false
  if (!feature.enabledToolTypes) return true
  return routeToolType.value !== null && feature.enabledToolTypes.includes(routeToolType.value)
}
</script>

<template>
  <div class="px-4 md:px-6 lg:px-8 pt-4">
    <nav
      aria-label="Feature navigation"
      class="dashboard-surface rounded-full px-1.5 py-1.5 flex gap-1 overflow-x-auto"
    >
      <template
        v-for="feature in features"
        :key="feature.label"
      >
        <NuxtLink
          v-if="isFeatureEnabled(feature) && feature.routeValue"
          :to="getFeatureRoute(feature.routeValue)"
          class="flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-medium rounded-full transition-colors duration-200"
          :class="activeFeature === feature.routeValue
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 sk-nav-accent'
            : 'text-zinc-600 ring-1 ring-zinc-200/80 hover:text-zinc-900 hover:bg-zinc-50 dark:text-zinc-400 dark:ring-zinc-700 dark:hover:text-zinc-100 dark:hover:bg-zinc-800/60'"
        >
          <UIcon
            :name="feature.icon"
            class="w-4 h-4"
          />
          {{ feature.label }}
          <UIcon
            v-if="feature.badgeIcon"
            :name="feature.badgeIcon"
            class="w-3.5 h-3.5 text-rose-400 dark:text-rose-300"
          />
        </NuxtLink>

        <span
          v-else
          aria-disabled="true"
          class="flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-medium rounded-full text-zinc-400 ring-1 ring-zinc-200/70 cursor-default dark:text-zinc-500 dark:ring-zinc-700/80"
        >
          <UIcon
            :name="feature.icon"
            class="w-4 h-4"
          />
          {{ feature.label }}
          <UIcon
            v-if="feature.badgeIcon"
            :name="feature.badgeIcon"
            class="w-3.5 h-3.5 text-rose-400 dark:text-rose-300"
          />
        </span>
      </template>
    </nav>
  </div>
</template>
