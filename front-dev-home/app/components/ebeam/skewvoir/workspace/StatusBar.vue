<template>
  <div class="flex items-center gap-4 border-t border-(--sk-border) bg-(--sk-surface) px-3 py-1.5 font-mono text-[10.5px] text-(--sk-ink-muted)">
    <span class="inline-flex items-center gap-1.5 font-semibold text-(--sk-ok)">
      <span class="h-1.5 w-1.5 rounded-full bg-(--sk-ok)" />
      READY
    </span>
    <span>conn: <span class="text-zinc-700 dark:text-zinc-300">{{ conn }}</span></span>
    <span>cache: <span class="text-zinc-700 dark:text-zinc-300">1.8 GB / 4 GB</span></span>
    <span>queue: <span class="text-zinc-700 dark:text-zinc-300">0 jobs</span></span>

    <div class="ml-auto flex items-center gap-4">
      <span>Mag <span class="text-zinc-700 dark:text-zinc-300">350K</span></span>
      <span>Vac <span class="text-zinc-700 dark:text-zinc-300">800V</span></span>
      <span>Pixel <span class="text-zinc-700 dark:text-zinc-300">1024×1024</span></span>
      <span>density · compact</span>
      <span class="font-semibold text-zinc-700 dark:text-zinc-300">{{ user }}</span>
      <span class="tabular-nums">{{ clock }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{ ws: SkewvoirWorkspace }>()

const user = 'KSH'
const conn = computed(() => `elastic-${props.ws.pinnedFilters.value.fab.toLowerCase()}`)

const now = ref(new Date())
let timer: ReturnType<typeof setInterval> | null = null

const clockFormatter = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Seoul',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false
})

// sv-SE gives "YYYY-MM-DD HH:mm"; tag it as KST to match the acquisition console.
const clock = computed(() => `${clockFormatter.format(now.value).replace(',', '')} KST`)

onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>
