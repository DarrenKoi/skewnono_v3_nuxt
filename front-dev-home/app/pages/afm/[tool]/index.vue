<template>
  <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl px-5 py-6 md:px-7 md:py-7">
      <div class="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
        <div class="min-w-0">
          <p class="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
            AFM Metrology
          </p>
          <h1 class="text-4xl font-semibold tracking-normal text-zinc-950 md:text-5xl dark:text-zinc-50">
            {{ toolLabel }}
          </h1>
          <p class="mt-2 text-base font-medium text-zinc-500 dark:text-zinc-400">
            <span v-if="fabLabel">{{ fabLabel }} fab</span>
            <span v-if="fabLabel && conceptLabel"> · </span>
            <span v-if="conceptLabel">{{ conceptLabel }}</span>
            <span v-if="fabLabel || conceptLabel"> · </span>
            row routes to a dedicated detail page
          </p>
        </div>
        <nav
          class="grid gap-4 sm:grid-cols-2 xl:flex xl:items-center"
          aria-label="AFM tool selector"
        >
          <div
            v-for="fabGroup in fabs"
            :key="fabGroup.fab"
            class="rounded-2xl border border-[var(--sk-border)] bg-[var(--sk-muted-surface)] px-4 py-3"
          >
            <span class="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-[0.18em] text-zinc-600 dark:text-zinc-300">
              <span class="h-2 w-2 rounded-full bg-[var(--sk-accent)]" />
              {{ fabGroup.fab }} FAB
            </span>
            <div class="flex flex-wrap gap-2">
              <UButton
                v-for="tool in fabGroup.tools"
                :key="tool.id"
                :to="afmToolHref(tool)"
                :aria-current="tool.id === toolId ? 'page' : undefined"
                size="sm"
                color="neutral"
                :variant="tool.id === toolId ? 'solid' : 'outline'"
                class="min-w-28 justify-center rounded-full px-5 text-base font-bold tracking-normal"
                :class="tool.id === toolId ? 'sk-nav-accent' : ''"
              >
                {{ tool.label }}
              </UButton>
            </div>
          </div>
        </nav>
      </div>
    </section>

    <div class="grid gap-6 lg:grid-cols-12">
      <div class="lg:col-span-7">
        <AfmSearchBar
          :tool-id="toolId"
          :is-in-group="cart.isInGroup"
          @add-to-group="cart.addToGroup"
          @view-details="onViewDetails"
        />
      </div>

      <div class="space-y-4 lg:col-span-5">
        <AfmViewHistoryCard
          :items="cart.viewHistory.value"
          @view-details="onViewDetails"
          @remove="cart.removeFromHistory"
          @clear="cart.clearHistory"
        />
        <AfmDataGroupingCard
          :items="cart.groupedData.value"
          @remove="cart.removeFromGroup"
          @clear="cart.clearGroup"
          @see-together="onSeeTogether"
          @save="onSaveGroup"
        />
        <AfmSavedGroupsCard
          :groups="cart.savedGroups.value"
          @load="cart.loadSavedGroup"
          @remove="cart.removeSavedGroup"
          @clear="cart.clearSavedGroups"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AfmMeasurement } from '~/composables/useAfmCart'

definePageMeta({
  layout: 'hub',
  key: route => route.path
})

const route = useRoute()
const { fabs, afmToolHref } = useAfmToolData()

const toolId = computed(() => String(route.params.tool ?? ''))

const matched = computed(() => {
  for (const fabGroup of fabs) {
    const tool = fabGroup.tools.find(t => t.id === toolId.value)
    if (tool) return { fab: fabGroup.fab, tool }
  }
  return null
})

const toolLabel = computed(() => matched.value?.tool.label ?? toolId.value.toUpperCase())
const fabLabel = computed(() => matched.value?.fab ?? '')
const conceptLabel = computed(() => matched.value?.tool.concept ?? '')

const cart = useAfmCart(toolId.value)

const onViewDetails = (measurement: AfmMeasurement) => {
  cart.addToHistory(measurement)
  navigateTo(`/afm/${toolId.value}/${encodeURIComponent(measurement.filename)}`)
}

const onSeeTogether = () => {
  navigateTo(`/afm/${toolId.value}/see-together`)
}

const onSaveGroup = (payload: { name: string, description: string }) => {
  cart.saveCurrentGroup(payload.name, payload.description)
}
</script>
