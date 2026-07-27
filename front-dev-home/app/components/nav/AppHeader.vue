<script setup lang="ts">
import type { HeaderLink } from '~/utils/headerNav'
import { useNavigationStore } from '~/stores/navigation'
import { fabSegment } from '~/utils/fab'
import { HEADER_LINKS } from '~/utils/headerNav'

const route = useRoute()
const nav = useNavigationStore()

const ACTIVE_CLASS = 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm sk-nav-accent'

// live-alarm is fab-scoped, so the top-nav icon jumps to the remembered
// tool/fab (default cd-sem / R3 before any ebeam visit). Only cd-sem and
// hv-sem have this board.
const liveAlarmTarget = computed(() => {
  const tt = nav.toolType.value === 'hv-sem' ? 'hv-sem' : 'cd-sem'
  return `/ebeam/${tt}/${fabSegment(nav.fab.value)}/live-alarm`
})

const linkTarget = (link: HeaderLink) => link.to ?? liveAlarmTarget.value

const isLinkActive = (link: HeaderLink) =>
  link.to === null
    ? !!link.activeMatch && route.path.includes(link.activeMatch)
    : route.path === link.to || route.path.startsWith(`${link.to}/`)
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
        v-for="link in HEADER_LINKS"
        :key="link.label"
        :to="linkTarget(link)"
        :icon="link.icon"
        color="neutral"
        variant="ghost"
        :aria-label="link.label"
        :aria-current="isLinkActive(link) ? 'page' : undefined"
        :class="isLinkActive(link) ? ACTIVE_CLASS : undefined"
      />
    </template>
  </UHeader>
</template>
