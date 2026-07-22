<script setup lang="ts">
import type { ToolType } from '~/stores/navigation'
import { FEATURE_SLUG_SUFFIX_REGEX, isFablessFeature } from '~/utils/features'

const route = useRoute()
const { fab, toolType: storeToolType } = useNavigation()
const isEbeamRoute = useEbeamRoute()

// Header-right info pages keep the feature tabs so the user can jump back to the main
// pages; outside ebeam routes the tool type falls back to the store's remembered value.
const INFO_PATHS = ['/intro', '/endpoints', '/activity', '/settings']
const isInfoRoute = computed(() =>
  INFO_PATHS.some(path => route.path === path || route.path.startsWith(`${path}/`))
)

type FeatureRouteValue = 'index' | 'recipe-search' | 'recipe-status' | 'hardware' | 'live-alarm' | 'device-statistics' | 'skewvoir' | 'skew-check'

type FeatureTab = {
  label: string
  icon: string
  routeValue?: FeatureRouteValue
  enabledToolTypes?: ToolType[]
}

const features: FeatureTab[] = [
  { label: '장비 상태', routeValue: 'index', icon: 'i-lucide-layout-dashboard', enabledToolTypes: ['cd-sem', 'hv-sem'] },
  { label: 'Recipe 현황', routeValue: 'recipe-status', icon: 'i-lucide-timer', enabledToolTypes: ['cd-sem', 'hv-sem'] },
  { label: 'Recipe 검색', routeValue: 'recipe-search', icon: 'i-lucide-search', enabledToolTypes: ['cd-sem', 'hv-sem'] },
  { label: 'H/W 관리', routeValue: 'hardware', icon: 'i-lucide-cpu', enabledToolTypes: ['cd-sem', 'hv-sem'] },
  { label: '라이브 알람', routeValue: 'live-alarm', icon: 'i-lucide-radio', enabledToolTypes: ['cd-sem', 'hv-sem'] },
  { label: '디바이스 통계', routeValue: 'device-statistics', icon: 'i-lucide-bar-chart-3', enabledToolTypes: ['cd-sem'] },
  // 스큐 관리 (skew-check) is hidden from the nav while its design is reworked.
  // The route and page still exist and remain reachable by URL.
  // { label: '스큐 관리', routeValue: 'skew-check', icon: 'i-lucide-git-compare', enabledToolTypes: ['cd-sem'] },
  { label: '스큐보아', routeValue: 'skewvoir', icon: 'i-lucide-eye', enabledToolTypes: ['cd-sem', 'hv-sem'] }
]

const toolTypes: ToolType[] = ['cd-sem', 'hv-sem', 'verity-sem', 'provision']

const routeToolType = computed<ToolType | null>(() => {
  const [, category, toolType] = route.path.split('/')
  if (category !== 'ebeam') return null
  return toolTypes.includes(toolType as ToolType) ? toolType as ToolType : null
})

const effectiveToolType = computed<ToolType | null>(() =>
  routeToolType.value ?? (isInfoRoute.value ? storeToolType.value : null)
)

const activeFeature = computed<FeatureRouteValue | null>(() => {
  if (!isEbeamRoute.value) return null
  const path = route.path
  if (path.includes('/recipe-search')) return 'recipe-search'
  if (path.includes('/recipe-status')) return 'recipe-status'
  if (path.includes('/hardware')) return 'hardware'
  if (path.includes('/live-alarm')) return 'live-alarm'
  if (path.includes('/device-statistics')) return 'device-statistics'
  if (path.includes('/skew-check')) return 'skew-check'
  if (path.includes('/skewvoir')) return 'skewvoir'
  return 'index'
})

const getFeatureRoute = (feature: string) => {
  const toolType = effectiveToolType.value
  if (!toolType) return route.path

  if (isFablessFeature(feature)) {
    return `/ebeam/${toolType}/${feature}`
  }

  // For fab-dependent features we need a fab segment in the URL. If the current path
  // doesn't have one (we're on a fabless feature page), fall back to the store's last fab,
  // and finally to the tool-type index — which redirects to the user's last-visited fab.
  const basePath = route.path.replace(FEATURE_SLUG_SUFFIX_REGEX, '')
  const pathFab = basePath.split('/')[3]
  const storeFab = fab.value && fab.value !== 'all' ? fab.value.toLowerCase() : ''
  const fabSegment = pathFab || storeFab

  if (!fabSegment) return `/ebeam/${toolType}`
  if (feature === 'index') return `/ebeam/${toolType}/${fabSegment}`
  return `/ebeam/${toolType}/${fabSegment}/${feature}`
}

const isFeatureEnabled = (feature: FeatureTab) => {
  if (!feature.routeValue) return false
  if (!feature.enabledToolTypes) return true
  return effectiveToolType.value !== null && feature.enabledToolTypes.includes(effectiveToolType.value)
}
</script>

<template>
  <nav
    v-if="isEbeamRoute || isInfoRoute"
    aria-label="Feature navigation"
    class="flex gap-1 min-w-0 overflow-x-auto"
  >
    <SkNavPill
      v-for="feature in features"
      :key="feature.label"
      :label="feature.label"
      :aria-label="feature.label"
      :icon="feature.icon"
      :active="activeFeature === feature.routeValue"
      :disabled="!isFeatureEnabled(feature)"
      :to="isFeatureEnabled(feature) && feature.routeValue ? getFeatureRoute(feature.routeValue) : undefined"
      size="sm"
      label-class="hidden lg:inline"
      :class="activeFeature === feature.routeValue ? 'shadow-sm sk-nav-accent' : undefined"
    />
  </nav>
</template>
