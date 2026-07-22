<script setup lang="ts">
import { useNavigationStore } from '~/stores/navigation'

const route = useRoute()
const colorMode = useColorMode()
const nav = useNavigationStore()

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

// live-alarm is fab-scoped, so the top-nav icon jumps to the remembered
// tool/fab (default cd-sem / R3 before any ebeam visit). Only cd-sem and
// hv-sem have this board.
const liveAlarmTarget = computed(() => {
  const tt = nav.toolType.value === 'hv-sem' ? 'hv-sem' : 'cd-sem'
  const fab = nav.fab.value && nav.fab.value !== 'all' ? nav.fab.value.toLowerCase() : 'r3'
  return `/ebeam/${tt}/${fab}/live-alarm`
})

const isLiveAlarmActive = computed(() => route.path.includes('/live-alarm'))
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
        to="/chat"
        icon="i-lucide-message-square"
        color="neutral"
        variant="ghost"
        aria-label="채팅"
        :aria-current="isActivePath('/chat') ? 'page' : undefined"
        :class="headerActionClass('/chat')"
      />
      <UButton
        :to="liveAlarmTarget"
        icon="i-lucide-radio"
        color="neutral"
        variant="ghost"
        aria-label="라이브 알람"
        :aria-current="isLiveAlarmActive ? 'page' : undefined"
        :class="isLiveAlarmActive ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm sk-nav-accent' : undefined"
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
