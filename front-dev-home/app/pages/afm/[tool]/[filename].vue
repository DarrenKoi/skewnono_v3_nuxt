<template>
  <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-5 md:p-6">
      <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div class="min-w-0">
          <p class="text-xs uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
            AFM · Recipe detail
          </p>
          <h1 class="truncate text-xl md:text-2xl font-semibold tracking-tight font-mono">
            {{ filename }}
          </h1>
          <p class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            {{ toolId.toUpperCase() }}
            <span v-if="information?.['Recipe ID']"> · {{ information['Recipe ID'] }}</span>
            <span v-if="information?.['Lot ID']"> · {{ information['Lot ID'] }}</span>
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <UButton
            :to="`/afm/${toolId}`"
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-arrow-left"
          >
            Back to search
          </UButton>
        </div>
      </div>
    </section>

    <div
      v-if="pending"
      class="dashboard-surface flex items-center justify-center gap-2 rounded-2xl px-4 py-16 text-sm text-zinc-500"
    >
      <UIcon name="i-lucide-loader-circle" class="h-4 w-4 animate-spin" />
      Loading measurement detail…
    </div>
    <div
      v-else-if="error"
      class="dashboard-surface rounded-2xl px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-300"
    >
      Failed to load measurement detail.
    </div>
    <template v-else-if="payload">
      <div class="grid gap-5 lg:grid-cols-12">
        <div class="space-y-5 lg:col-span-5">
          <AfmDetailInfoPanel
            :information="information"
            :summary="payload.summary"
          />
          <AfmDetailMeasurementPointsTable
            :data="payload.data"
            :available-points="payload.available_points"
            :selected-point="selectedPoint"
            @update:selected-point="selectedPoint = $event"
          />
        </div>
        <div class="space-y-5 lg:col-span-7">
          <AfmDetailSummaryScatterChart :summary="payload.summary" />
          <div class="grid gap-5 md:grid-cols-2">
            <AfmDetailHeatmapChart
              :profile="profile"
              :loading="profilePending"
            />
            <AfmDetailHistogramChart
              :profile="profile"
              :loading="profilePending"
            />
          </div>
          <AfmDetailProfileImage
            :url="imageUrl"
            :point="selectedPoint"
            :loading="imagePending"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'

definePageMeta({
  layout: 'hub',
  key: route => route.path
})

const route = useRoute()
const toolId = computed(() => String(route.params.tool ?? ''))
const filename = computed(() => String(route.params.filename ?? ''))
const toolName = computed(() => toolId.value.toUpperCase())

const { useAfmDetail, fetchProfile, fetchImage } = useAfmDetailApi()

const { data: detailResponse, pending, error } = await useAfmDetail(toolName.value, filename.value)

const payload = computed(() => detailResponse.value?.data)
const information = computed(() => payload.value?.information ?? {})

const selectedPoint = ref<string>('')

watch(payload, (next) => {
  if (next?.available_points?.length && !selectedPoint.value) {
    selectedPoint.value = next.available_points[0] ?? ''
  }
}, { immediate: true })

const useTokenedLoader = <T, R>(
  fetcher: (point: string) => Promise<T>,
  extract: (res: T) => R,
  empty: R
) => {
  const data = ref(empty) as Ref<R>
  const pending = ref(false)
  let token = 0

  const run = async (point: string) => {
    const t = ++token
    data.value = empty
    if (!point) {
      pending.value = false
      return
    }
    pending.value = true
    try {
      const res = await fetcher(point)
      if (t === token) data.value = extract(res)
    } catch {
      if (t === token) data.value = empty
    } finally {
      if (t === token) pending.value = false
    }
  }

  return { data, pending, run }
}

const profileLoader = useTokenedLoader(
  (point: string) => fetchProfile(toolName.value, filename.value, point),
  res => res.data ?? [],
  [] as AfmProfilePoint[]
)
const imageLoader = useTokenedLoader(
  (point: string) => fetchImage(toolName.value, filename.value, point),
  res => res.data?.url ?? null,
  null as string | null
)

const profile = profileLoader.data
const profilePending = profileLoader.pending
const imageUrl = imageLoader.data
const imagePending = imageLoader.pending

watch(selectedPoint, (point) => {
  profileLoader.run(point)
  imageLoader.run(point)
}, { immediate: true })
</script>
