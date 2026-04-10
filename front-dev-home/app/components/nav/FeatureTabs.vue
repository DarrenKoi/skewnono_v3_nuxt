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
  <div class="px-4 md:px-6 lg:px-8 pt-4">
    <nav
      aria-label="Feature navigation"
      class="dashboard-surface rounded-2xl px-2 py-2 flex gap-1 overflow-x-auto"
    >
      <NuxtLink
        v-for="feature in features"
        :key="feature.value"
        :to="getFeatureRoute(feature.value)"
        class="flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl transition-all duration-200"
        :class="activeFeature === feature.value
          ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
          : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100/80 dark:hover:bg-zinc-800/60'"
      >
        <UIcon
          :name="feature.icon"
          class="w-4 h-4"
        />
        {{ feature.label }}
      </NuxtLink>
    </nav>
  </div>
</template>
