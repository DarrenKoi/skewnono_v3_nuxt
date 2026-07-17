<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-image"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Profile image
          </h2>
        </div>
        <div class="flex items-center gap-2">
          <UBadge
            v-if="point"
            :label="`Point ${point}`"
            color="primary"
            size="xs"
            variant="subtle"
          />
          <UButton
            v-if="url"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-download"
            aria-label="Download profile image"
            @click="downloadImage"
          />
        </div>
      </div>
    </template>

    <div
      v-if="loading"
      class="flex h-72 items-center justify-center sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mr-2 h-4 w-4 animate-spin"
      />
      Loading image…
    </div>
    <div
      v-else-if="!url"
      class="flex h-72 flex-col items-center justify-center text-center sk-body"
    >
      <UIcon
        name="i-lucide-image-off"
        class="mb-2 h-8 w-8 text-(--sk-ink-muted)"
      />
      No profile image available
    </div>
    <div
      v-else
      class="flex h-72 items-center justify-center overflow-hidden rounded-xl bg-zinc-50 dark:bg-zinc-900"
    >
      <img
        :src="url"
        :alt="`Profile image for ${point}`"
        class="max-h-full max-w-full object-contain"
      >
    </div>
  </UCard>
</template>

<script setup lang="ts">
const props = defineProps<{
  url: string | null
  point: string
  filename: string
  loading?: boolean
}>()

const downloadImage = async () => {
  if (!import.meta.client || !props.url) return
  try {
    const res = await fetch(props.url)
    const blob = await res.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    const safePoint = props.point.replace(/[^a-zA-Z0-9]+/g, '_') || 'point'
    link.download = `${props.filename}-point${safePoint}.svg`
    link.click()
    URL.revokeObjectURL(objectUrl)
  } catch {
    // Best-effort download; a failed fetch simply does nothing.
  }
}
</script>
