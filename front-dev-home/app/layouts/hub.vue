<template>
  <div class="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
    <UHeader>
      <template #left>
        <NuxtLink to="/" class="flex items-center">
          <AppLogo />
        </NuxtLink>
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

    <main class="flex-1">
      <slot />
    </main>

    <footer class="border-t border-gray-200 dark:border-gray-700 py-4">
      <div class="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
        SKEWNONO v3 - E-Beam Metrology Dashboard
      </div>
    </footer>
  </div>
</template>
