<template>
  <!-- These sub-tabs change the route, so they stay real links (NuxtLink +
       aria-current="page"), which is the correct semantic for a link that owns
       the view. Visually they wear the SAME segmented-track skin as the
       전체 요약/디바이스별 toggle in Recipe TAT / Fail Issue (tinted rail, active
       pill lifts on a white surface) so the two selection rows read as one family. -->
  <nav
    aria-label="장비 상태 sub-view"
    class="inline-flex items-center gap-1 rounded-lg bg-zinc-100/70 p-1 dark:bg-zinc-800/60"
  >
    <NuxtLink
      v-for="option in options"
      :key="option.value"
      :to="option.to"
      :aria-current="active === option.value ? 'page' : undefined"
      class="inline-flex h-9 items-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors"
      :class="active === option.value
        ? 'bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200/80 dark:bg-zinc-900 dark:text-zinc-50 dark:ring-zinc-700/80'
        : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
    >
      <UIcon
        :name="option.icon"
        class="h-4 w-4"
      />
      {{ option.label }}
    </NuxtLink>
  </nav>
</template>

<script setup lang="ts">
const SUB_TABS = [
  { value: 'list', label: '장비 리스트', icon: 'i-lucide-server' },
  { value: 'storage', label: '스토리지', icon: 'i-lucide-hard-drive' }
] as const

type SubTabValue = typeof SUB_TABS[number]['value']

const route = useRoute()

const isStorage = computed(() => route.path.includes('/storage'))
const basePath = computed(() => isStorage.value ? route.path.replace(/\/storage(\/.*)?$/, '') : route.path)
const active = computed<SubTabValue>(() => isStorage.value ? 'storage' : 'list')

const options = computed(() =>
  SUB_TABS.map(tab => ({
    ...tab,
    to: tab.value === 'storage' ? `${basePath.value}/storage` : basePath.value
  }))
)
</script>
