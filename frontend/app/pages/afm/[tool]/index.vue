<template>
  <div class="space-y-6">
    <EbeamMetaBar
      :eyebrow="fab ? `AFM · ${fab}` : 'AFM'"
      title="AFM 측정 검색"
    >
      <template #toggle>
        <nav
          class="flex flex-wrap gap-1"
          aria-label="AFM 장비"
        >
          <SkNavPill
            v-for="tool in fabs.flatMap(group => group.tools)"
            :key="tool.id"
            size="sm"
            :to="afmToolHref(tool)"
            :active="tool.id === toolId"
            :label="tool.label"
          />
        </nav>
      </template>
      <template #actions>
        <UButton
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-pen-tool"
          label="팁 모니터링"
          :to="`/afm/${toolId}/tips`"
        />
      </template>
    </EbeamMetaBar>

    <div class="grid gap-6 lg:grid-cols-12">
      <AfmSearchBar
        class="lg:col-span-7 2xl:col-span-8"
        :tool-id="toolId"
        @view-details="onViewDetails"
      />

      <div class="space-y-6 lg:col-span-5 2xl:col-span-4">
        <AfmViewHistoryCard
          :tool-id="toolId"
          @view-details="onViewDetails"
        />
        <AfmDataGroupingCard :tool-id="toolId" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AfmMeasurement } from '~/composables/useAfmCart'

// `key` remounts the page per tool, so the route params are read once.
definePageMeta({
  key: route => route.path
})

const toolId = String(useRoute().params.tool ?? '')
const { fabs, afmToolHref } = useAfmToolData()
const fab = fabs.find(group => group.tools.some(tool => tool.id === toolId))?.fab

const cart = useAfmCart(toolId)

const onViewDetails = (measurement: AfmMeasurement) => {
  cart.addToHistory(measurement)
  navigateTo(`/afm/${toolId}/${encodeURIComponent(measurement.filename)}`)
}
</script>
