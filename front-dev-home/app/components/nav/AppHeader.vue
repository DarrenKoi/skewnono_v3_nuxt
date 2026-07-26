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
      <!-- scan-search: 스캔 프레임(FOV) 안의 돋보기(배율) — 이 페이지가 답하는
           "패턴이 화면에 들어오는 한도에서 가장 높은 배율" 그 자체다. 자(ruler)는
           길이를 재는 뜻이라 배율·픽셀 선택과는 어긋났다. 헤더의 다른 돋보기
           (search)는 항상 'Recipe 검색' 텍스트 필 안에 있어 아이콘만 있는 이
           묶음과 헷갈리지 않는다. -->
      <UButton
        to="/mag-pixel"
        icon="i-lucide-scan-search"
        color="neutral"
        variant="ghost"
        aria-label="Mag/Pixel 가이드"
        :aria-current="isActivePath('/mag-pixel') ? 'page' : undefined"
        :class="headerActionClass('/mag-pixel')"
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
