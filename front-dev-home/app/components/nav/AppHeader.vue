<script setup lang="ts">
const route = useRoute()
const colorMode = useColorMode()

const isActivePath = (path: string) =>
  route.path === path || route.path.startsWith(`${path}/`)

const headerActionClass = (path: string) =>
  isActivePath(path)
    ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm sk-nav-accent'
    : undefined

const isDark = computed(() => colorMode.value === 'dark')

const toggleColorMode = () => {
  colorMode.preference = isDark.value ? 'light' : 'dark'
}
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
        to="/intro"
        icon="i-lucide-panels-top-left"
        color="neutral"
        variant="ghost"
        aria-label="소개"
        :aria-current="isActivePath('/intro') ? 'page' : undefined"
        :class="headerActionClass('/intro')"
      />
      <UButton
        to="/endpoints"
        icon="i-lucide-plug"
        color="neutral"
        variant="ghost"
        aria-label="API 리스트"
        :aria-current="isActivePath('/endpoints') ? 'page' : undefined"
        :class="headerActionClass('/endpoints')"
      />
      <UButton
        to="/activity"
        icon="i-lucide-bar-chart-3"
        color="neutral"
        variant="ghost"
        aria-label="사용 통계"
        :aria-current="isActivePath('/activity') ? 'page' : undefined"
        :class="headerActionClass('/activity')"
      />
      <UButton
        to="/settings"
        icon="i-lucide-settings"
        color="neutral"
        variant="ghost"
        aria-label="세팅"
        :aria-current="isActivePath('/settings') ? 'page' : undefined"
        :class="headerActionClass('/settings')"
      />
      <UButton
        :icon="isDark ? 'i-lucide-moon' : 'i-lucide-sun'"
        color="neutral"
        variant="ghost"
        :aria-label="isDark ? '다크 모드' : '밝은 모드'"
        @click="toggleColorMode"
      />
    </template>
  </UHeader>
</template>
