<template>
  <div class="max-w-5xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-6 md:p-8">
      <p class="sk-eyebrow mb-2">
        AFM Metrology
      </p>
      <h1 class="sk-page-title">
        Tool 선택
      </h1>
    </section>

    <UCard
      class="dashboard-surface rounded-3xl"
      :ui="{ body: 'p-6' }"
    >
      <nav class="space-y-3">
        <div
          v-for="fabGroup in fabs"
          :key="fabGroup.fab"
          class="space-y-1"
        >
          <div class="px-3 sk-label">
            {{ fabGroup.fab }}
          </div>
          <NuxtLink
            v-for="tool in fabGroup.tools"
            :key="tool.id"
            :to="afmToolHref(tool)"
            class="flex items-center justify-between p-3 rounded-xl hover:bg-zinc-100 dark:hover:bg-zinc-800/80 transition-colors group"
          >
            <span class="flex items-center gap-2">
              <UIcon
                name="i-lucide-arrow-right"
                class="w-4 h-4 text-(--sk-ink-muted) group-hover:text-zinc-800 dark:group-hover:text-zinc-200 transition-colors"
              />
              <span class="font-medium">{{ tool.label }}</span>
            </span>
            <UBadge
              :label="fabGroup.fab"
              color="neutral"
              variant="subtle"
            />
          </NuxtLink>
        </div>
      </nav>
    </UCard>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})

const { fabs, afmToolHref } = useAfmToolData()
</script>
