<template>
  <nav
    class="flex items-center gap-1.5 sk-eyebrow"
    aria-label="Breadcrumb"
  >
    <NuxtLink
      to="/afm"
      class="transition-colors hover:text-(--sk-ink)"
    >
      AFM
    </NuxtLink>
    <UIcon
      name="i-lucide-chevron-right"
      class="h-3 w-3 opacity-60"
    />
    <NuxtLink
      :to="`/afm/${tool}`"
      class="transition-colors hover:text-(--sk-ink)"
    >
      {{ tool.toUpperCase() }}
    </NuxtLink>
    <template v-if="current">
      <UIcon
        name="i-lucide-chevron-right"
        class="h-3 w-3 opacity-60"
      />
      <span class="max-w-[60vw] truncate text-(--sk-ink-muted)">
        {{ current }}
      </span>
    </template>
  </nav>
</template>

<script setup lang="ts">
// Compact AFM navigation breadcrumb (AFM › TOOL › current), styled to sit where
// the static sk-eyebrow label used to be on the detail / see-together headers.
defineProps<{
  tool: string
  current?: string
}>()
</script>
