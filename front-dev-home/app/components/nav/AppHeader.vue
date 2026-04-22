<script setup lang="ts">
const { category, navigateToCategory } = useNavigation()

const categories = [
  { id: 'ebeam' as const, label: 'E-Beam', enabled: true },
  { id: 'thickness' as const, label: 'Thickness', enabled: false }
]
</script>

<template>
  <UHeader>
    <template #left>
      <NuxtLink
        to="/"
        class="flex items-center"
      >
        <AppLogo />
      </NuxtLink>

      <nav
        aria-label="Category navigation"
        class="hidden md:flex items-center gap-1 rounded-full border border-(--sk-border) bg-(--sk-surface) p-1 ml-6 shadow-[0_1px_0_rgba(9,9,11,0.03)]"
      >
        <button
          v-for="cat in categories"
          :key="cat.id"
          :aria-pressed="category === cat.id"
          :aria-disabled="!cat.enabled"
          :disabled="!cat.enabled"
          type="button"
          class="px-4 py-2 text-sm font-medium rounded-full transition-colors duration-200"
          :class="category === cat.id
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900'
            : !cat.enabled
              ? 'text-zinc-400 ring-1 ring-zinc-200/70 cursor-not-allowed dark:text-zinc-500 dark:ring-zinc-700/80'
              : 'text-zinc-600 ring-1 ring-zinc-200/90 hover:text-zinc-900 dark:text-zinc-400 dark:ring-zinc-700 dark:hover:text-zinc-100'"
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
