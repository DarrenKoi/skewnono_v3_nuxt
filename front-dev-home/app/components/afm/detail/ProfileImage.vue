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
            class="h-4 w-4 text-zinc-500"
          />
          <h2 class="text-sm font-semibold">
            Profile image
          </h2>
        </div>
        <UBadge
          v-if="point"
          :label="`Point ${point}`"
          color="primary"
          size="xs"
          variant="subtle"
        />
      </div>
    </template>

    <div
      v-if="loading"
      class="flex h-72 items-center justify-center text-sm text-zinc-500"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mr-2 h-4 w-4 animate-spin"
      />
      Loading image…
    </div>
    <div
      v-else-if="!url"
      class="flex h-72 flex-col items-center justify-center text-center text-sm text-zinc-500"
    >
      <UIcon
        name="i-lucide-image-off"
        class="mb-2 h-8 w-8 text-zinc-400"
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
defineProps<{
  url: string | null
  point: string
  loading?: boolean
}>()
</script>
