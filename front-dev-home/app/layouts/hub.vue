<script setup lang="ts">
const route = useRoute()

const isActivePath = (path: string) =>
  route.path === path || route.path.startsWith(`${path}/`)

const headerActionClass = (path: string) =>
  isActivePath(path)
    ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm sk-nav-accent'
    : undefined
</script>

<template>
  <div class="relative isolate min-h-screen flex flex-col text-zinc-900 dark:text-zinc-100">
    <div
      class="dashboard-bg-layer"
      aria-hidden="true"
    />
    <UHeader>
      <template #left>
        <NuxtLink
          to="/"
          class="flex items-center"
        >
          <AppLogo />
        </NuxtLink>
      </template>

      <template #right>
        <UButton
          to="/intro"
          icon="i-lucide-panels-top-left"
          color="neutral"
          variant="ghost"
          aria-label="소개"
          :aria-current="isActivePath('/intro') ? 'page' : undefined"
          :class="headerActionClass('/intro')"
        >
          <span class="hidden sm:inline">
            소개
          </span>
        </UButton>
        <UButton
          to="/information"
          icon="i-lucide-plug"
          color="neutral"
          variant="ghost"
          aria-label="API 리스트"
          :aria-current="isActivePath('/information') ? 'page' : undefined"
          :class="headerActionClass('/information')"
        >
          <span class="hidden sm:inline">
            API
          </span>
        </UButton>
        <UButton
          to="/activity"
          icon="i-lucide-bar-chart-3"
          color="neutral"
          variant="ghost"
          aria-label="사용 통계"
          :aria-current="isActivePath('/activity') ? 'page' : undefined"
          :class="headerActionClass('/activity')"
        >
          <span class="hidden sm:inline">
            통계
          </span>
        </UButton>
        <UButton
          to="/settings"
          icon="i-lucide-settings"
          color="neutral"
          variant="ghost"
          aria-label="Settings"
          :aria-current="isActivePath('/settings') ? 'page' : undefined"
          :class="headerActionClass('/settings')"
        />
        <UColorModeButton />
      </template>
    </UHeader>

    <main class="flex-1">
      <slot />
    </main>

    <footer class="border-t-(--sk-border) py-4">
      <div class="max-w-7xl mx-auto px-4 text-center text-sm text-zinc-500 dark:text-zinc-400">
        SKEWNONO v3 - Metrology Solution
      </div>
    </footer>
  </div>
</template>
