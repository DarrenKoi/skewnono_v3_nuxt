<script setup lang="ts">
const route = useRoute()

const features = [
  { label: 'Dashboard', value: 'index', icon: 'i-lucide-layout-dashboard' },
  { label: 'Monitor', value: 'monitor', icon: 'i-lucide-activity' },
  { label: 'Analysis', value: 'analysis', icon: 'i-lucide-bar-chart-3' },
  { label: 'Reports', value: 'reports', icon: 'i-lucide-file-text' }
]

const activeFeature = computed(() => {
  const path = route.path
  if (path.includes('/monitor')) return 'monitor'
  if (path.includes('/analysis')) return 'analysis'
  if (path.includes('/reports')) return 'reports'
  return 'index'
})

const getFeatureRoute = (feature: string) => {
  const basePath = route.path.replace(/\/(monitor|analysis|reports)$/, '')
  if (feature === 'index') return basePath
  return `${basePath}/${feature}`
}
</script>

<template>
  <div class="border-b border-gray-200 dark:border-gray-700 px-4 pt-2">
    <nav class="flex gap-1">
      <NuxtLink
        v-for="feature in features"
        :key="feature.value"
        :to="getFeatureRoute(feature.value)"
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px"
        :class="activeFeature === feature.value
          ? 'border-primary-500 text-primary-600 dark:text-primary-400'
          : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:border-gray-300'"
      >
        <UIcon :name="feature.icon" class="w-4 h-4" />
        {{ feature.label }}
      </NuxtLink>
    </nav>
  </div>
</template>
