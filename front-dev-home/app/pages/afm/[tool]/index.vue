<template>
  <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-6 md:p-8">
      <div class="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
            AFM Metrology
          </p>
          <h1 class="text-2xl md:text-3xl font-semibold tracking-tight">
            {{ toolLabel }}
          </h1>
          <p
            v-if="fabLabel"
            class="text-sm text-zinc-500 dark:text-zinc-400 mt-1"
          >
            {{ fabLabel }} fab
          </p>
        </div>
        <nav
          class="flex flex-wrap items-end gap-x-6 gap-y-3"
          aria-label="AFM tool selector"
        >
          <div
            v-for="fabGroup in fabs"
            :key="fabGroup.fab"
            class="flex flex-col items-start gap-1.5"
          >
            <span class="text-[11px] uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400 font-semibold">
              {{ fabGroup.fab }}
            </span>
            <div class="flex flex-wrap gap-1.5">
              <UButton
                v-for="tool in fabGroup.tools"
                :key="tool.id"
                :to="afmToolHref(tool)"
                :aria-current="tool.id === toolId ? 'page' : undefined"
                size="xs"
                :color="tool.id === toolId ? 'primary' : 'neutral'"
                :variant="tool.id === toolId ? 'solid' : 'outline'"
                class="rounded-full"
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

const cart = useAfmCart(toolId.value)

const onViewDetails = (measurement: AfmMeasurement) => {
  cart.addToHistory(measurement)
}

const onSaveGroup = (payload: { name: string, description: string }) => {
  cart.saveCurrentGroup(payload.name, payload.description)
}
</script>
