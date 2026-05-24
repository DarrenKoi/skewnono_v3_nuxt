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
  <UHeader>
    <template #left>
      <NuxtLink
        to="/"
        class="flex items-center"
      >
        <AppLogo />
      </NuxtLink>
    </template>

    <NavFeatureTabs />

    <template #right>
      <UButton
        to="/information"
        icon="i-lucide-info"
        color="neutral"
        variant="ghost"
        aria-label="프로젝트 정보"
        :aria-current="isActivePath('/information') ? 'page' : undefined"
        :class="headerActionClass('/information')"
      >
        <span class="hidden sm:inline">
          정보
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
</template>
