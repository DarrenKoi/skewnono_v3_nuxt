<template>
  <nav
    class="space-y-3"
    aria-label="AFM 장비"
  >
    <div
      v-for="fabGroup in fabs"
      :key="fabGroup.fab"
      class="space-y-1"
    >
      <p class="px-3 sk-label">
        {{ fabGroup.fab }}
      </p>
      <NuxtLink
        v-for="tool in fabGroup.tools"
        :key="tool.id"
        :to="afmToolHref(tool)"
        class="group flex items-center gap-2 rounded-(--sk-r-nav) p-3 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
      >
        <UIcon
          name="i-lucide-arrow-right"
          class="size-4 text-(--sk-ink-muted) transition-colors duration-200 group-hover:text-(--sk-ink)"
        />
        <span class="font-medium">{{ tool.label }}</span>
      </NuxtLink>
    </div>
  </nav>
</template>

<script setup lang="ts">
// Fab-grouped links to each AFM tool's search page. Shared by the landing-page
// card and /afm so the two lists cannot drift.
const { fabs, afmToolHref } = useAfmToolData()
</script>
