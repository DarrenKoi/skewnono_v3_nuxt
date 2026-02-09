<script setup lang="ts">
const { category, navigateToCategory } = useNavigation()

const categories = [
  { id: 'ebeam' as const, label: 'E-Beam' },
  { id: 'thickness' as const, label: 'Thickness' }
]
</script>

<template>
  <UHeader>
    <template #left>
      <NuxtLink to="/" class="flex items-center">
        <AppLogo />
      </NuxtLink>

      <div class="hidden md:flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 ml-6">
        <button
          v-for="cat in categories"
          :key="cat.id"
          class="px-4 py-1.5 text-sm font-medium rounded-md transition-colors"
          :class="category === cat.id
            ? 'bg-white dark:bg-gray-700 text-primary-600 dark:text-primary-400 shadow-sm'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'"
          @click="navigateToCategory(cat.id)"
        >
          {{ cat.label }}
        </button>
      </div>
    </template>

    <template #right>
      <UButton
        icon="i-lucide-search"
        color="neutral"
        variant="ghost"
        aria-label="Search"
      />
      <UButton
        to="/settings"
        icon="i-lucide-settings"
        color="neutral"
        variant="ghost"
        aria-label="Settings"
      />
      <UColorModeButton />
    </template>
  </UHeader>
</template>
