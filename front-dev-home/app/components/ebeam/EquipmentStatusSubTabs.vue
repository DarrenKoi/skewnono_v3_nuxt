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
import type { ToolType } from '~/utils/toolType'
import { hasStorageView } from '~/utils/toolType'

const SUB_TABS = [
  { value: 'list', label: '장비 리스트', icon: 'i-lucide-server' },
  { value: 'storage', label: '스토리지', icon: 'i-lucide-hard-drive' }
] as const

type SubTabValue = typeof SUB_TABS[number]['value']

// 어느 계열인지는 경로에서 되짚지 않고 부모가 넘깁니다 — ToolInventoryView 와
// StorageView 는 이미 toolType 을 들고 있고, 경로를 다시 파싱하면 라우트 구조가
// 바뀔 때마다 같이 깨집니다.
const props = defineProps<{ toolType: ToolType }>()

const route = useRoute()

const isStorage = computed(() => route.path.includes('/storage'))
const basePath = computed(() => isStorage.value ? route.path.replace(/\/storage(\/.*)?$/, '') : route.path)
const active = computed<SubTabValue>(() => isStorage.value ? 'storage' : 'list')

// 링크를 그릴지 말지는 라우트가 있느냐로 정합니다. AMAT 계열에는 스토리지
// 페이지가 없어서, 무조건 그리면 클릭이 아무 데도 가지 않고 라우터 경고만
// 남습니다. 탭을 지우는 판단 자체는 이 컴포넌트가 집니다 — 링크의 주인이
// 여기라서, 호출부가 무엇을 넘기든 없는 라우트로는 링크하지 않습니다.
const availableTabs = computed(() =>
  SUB_TABS.filter(tab => tab.value !== 'storage' || hasStorageView(props.toolType))
)

const options = computed(() =>
  availableTabs.value.map(tab => ({
    ...tab,
    to: tab.value === 'storage' ? `${basePath.value}/storage` : basePath.value
  }))
)
</script>
