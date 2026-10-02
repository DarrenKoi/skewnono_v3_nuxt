<template>
  <nav
    class="space-y-3"
    aria-label="AFM 장비"
  >
    <div
      v-for="fabGroup in fabs"
      :key="fabGroup.fab"
      :class="tiles ? 'space-y-2' : 'space-y-1'"
    >
      <p
        class="sk-label"
        :class="tiles ? 'text-xs' : 'px-3'"
      >
        {{ fabGroup.fab }}
      </p>
      <NuxtLink
        v-for="tool in fabGroup.tools"
        :key="tool.id"
        :to="afmToolHref(tool)"
        class="group flex items-center gap-2 rounded-(--sk-r-nav) transition-colors duration-200 hover:bg-(--sk-muted-surface)"
        :class="tiles ? 'border border-(--sk-border) px-4 py-3.5' : 'p-3'"
      >
        <UIcon
          v-if="!tiles"
          name="i-lucide-arrow-right"
          class="size-4 text-(--sk-ink-muted) transition-colors duration-200 group-hover:text-(--sk-ink)"
        />
        <span :class="tiles ? 'flex-1 font-mono text-base font-semibold text-(--sk-ink)' : 'font-medium'">{{ tool.label }}</span>
        <span
          v-if="tiles"
          class="sk-meta transition-colors duration-200 group-hover:text-(--sk-ink)"
        >측정 검색</span>
        <UIcon
          v-if="tiles"
          name="i-lucide-arrow-right"
          class="size-4 text-(--sk-ink-muted) transition-colors duration-200 group-hover:text-(--sk-ink)"
        />
      </NuxtLink>
    </div>
  </nav>
</template>

<script setup lang="ts">
// Fab-grouped links to each AFM tool's search page. Shared by the landing-page
// card and /afm so the two lists cannot drift; `tiles` is the /afm form, where
// the list is the whole page and each tool is a bordered target.
defineProps<{
  tiles?: boolean
}>()

const { fabs, afmToolHref } = useAfmToolData()
</script>
