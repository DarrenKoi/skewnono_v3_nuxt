<template>
  <div
    v-if="visible.length > 0"
    class="flex flex-col gap-2 px-4 md:px-6 lg:px-8 pt-3"
  >
    <UAlert
      v-for="item in visible"
      :key="item.id"
      :color="colorFor(item.level)"
      variant="subtle"
      :title="item.title"
      :description="item.body"
      :close="item.dismissible ? { color: 'neutral', variant: 'link' } : undefined"
      @update:open="(open: boolean) => !open && dismiss(item.id)"
    />
  </div>
</template>

<script setup lang="ts">
import type { AnnouncementLevel } from '~/composables/useAnnouncementsApi'

const STORAGE_KEY = 'sk:dismissed_announcement_ids'

const { data } = useAnnouncements()

const dismissedIds = ref<Set<string>>(new Set())

onMounted(() => {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return
  try {
    const arr = JSON.parse(raw)
    if (Array.isArray(arr)) dismissedIds.value = new Set(arr.filter(x => typeof x === 'string'))
  } catch {
    // ignore corrupt storage
  }
})

const visible = computed(() => (data.value ?? []).filter(a => !dismissedIds.value.has(a.id)))

const dismiss = (id: string) => {
  const next = new Set(dismissedIds.value)
  next.add(id)
  dismissedIds.value = next
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]))
}

const colorFor = (level: AnnouncementLevel): 'info' | 'warning' | 'error' => {
  if (level === 'critical') return 'error'
  if (level === 'warning') return 'warning'
  return 'info'
}
</script>
