<script setup lang="ts">
const { category, navigateToCategory } = useNavigation()

const categories = [
  { id: 'ebeam' as const, label: 'E-Beam' },
  { id: 'thickness' as const, label: 'Thickness' }
]
</script>

<template>
  <UHeader class="dashboard-surface border-b border-zinc-200/70 dark:border-zinc-800/70">
    <template #left>
      <NuxtLink
        to="/"
        class="flex items-center"
      >
        <AppLogo />
      </NuxtLink>

      <nav
        aria-label="Category navigation"
        class="hidden md:flex items-center gap-1 rounded-xl p-1.5 ml-6 border border-zinc-200/80 dark:border-zinc-800/80 bg-white/60 dark:bg-zinc-900/45 backdrop-blur"
      >
        <button
          v-for="cat in categories"
          :key="cat.id"
          :aria-pressed="category === cat.id"
          type="button"
          class="px-4 py-1.5 text-sm font-medium rounded-lg transition-all duration-200"
          :class="category === cat.id
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
            : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200'"
          @click="navigateToCategory(cat.id)"
        >
          {{ cat.label }}
        </button>
      </nav>
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
