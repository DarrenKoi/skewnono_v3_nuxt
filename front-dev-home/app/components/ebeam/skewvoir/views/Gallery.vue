<template>
  <EbeamSkewvoirPanelFrame
    title="SEM Gallery"
    :meta="frameMeta"
    icon="i-lucide-images"
  >
    <!-- Loading -->
    <div
      v-if="analysis.focusPending.value"
      class="flex h-96 items-center justify-center gap-2 sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>

    <!-- ── SINGLE scope: priority visual-evidence review queue ─────────────── -->
    <div
      v-else-if="analysis.scope.value === 'single'"
      class="flex flex-col gap-3"
    >
      <EbeamSkewvoirGalleryReviewFilters
        v-model="filter"
        :counts="filterCounts"
      />

      <p
        v-if="queue.readiness.residual !== 'ok'"
        class="rounded-(--sk-r-nav) border border-(--sk-border-soft) bg-(--sk-chip-bg)/40 px-3 py-2 sk-meta"
      >
        {{ queue.readiness.reason }}
      </p>

      <div
        v-if="filteredEntries.length"
        class="grid max-h-[34rem] grid-cols-2 gap-2 overflow-auto sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
      >
        <EbeamSkewvoirGalleryEvidenceCard
          v-for="entry in filteredEntries"
          :key="`${entry.chip}#${entry.sequence}`"
          :entry="entry"
          :src="entry.image ? msrImageUrl(entry.image) : null"
          :focused="entry.chip === analysis.focusedSite.value"
          @open="openViewer(entry)"
          @focus="focusSite(entry)"
        />
      </div>
      <div
        v-else
        class="flex h-72 items-center justify-center sk-body"
      >
        {{ queue.entries.length ? '필터에 해당하는 항목이 없습니다.' : `${analysis.activeParam.value} 근거 항목이 없습니다.` }}
      </div>
    </div>

    <!-- ── SET scope: existing focus-only filename grid (Task 12 replaces) ──── -->
    <div
      v-else-if="images.length"
      class="grid max-h-[34rem] grid-cols-3 gap-2 overflow-auto sm:grid-cols-4 xl:grid-cols-6"
    >
      <figure
        v-for="img in images"
        :key="img.name"
        class="overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
      >
        <img
          :src="msrImageUrl(img.name)"
          :alt="img.name"
          class="aspect-square w-full object-cover"
          loading="lazy"
        >
        <figcaption class="truncate px-1.5 py-1 sk-meta">
          {{ img.chip }} · {{ img.cd.toFixed(2) }}
        </figcaption>
      </figure>
    </div>
    <div
      v-else
      class="flex h-96 items-center justify-center sk-body"
    >
      {{ analysis.activeParam.value }} 이미지가 없습니다.
    </div>

    <!-- Enlarged viewer + measurement-evidence drawer (single scope). -->
    <EbeamSkewvoirGalleryImageViewer
      :open="viewerOpen"
      :entries="filteredEntries"
      :index="viewerIndex"
      :geo="analysis.waferGeo.value"
      @update:index="viewerIndex = $event"
      @close="viewerOpen = false"
      @move-to-site="onMoveToSite"
      @evidence="onEvidence"
    />
    <EbeamSkewvoirGalleryImageEvidenceDrawer
      v-model:open="drawerOpen"
      :entry="drawerEntry"
    />
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { ReviewFilter } from '~/components/ebeam/skewvoir/gallery/ReviewFilters.vue'
import { measuredRows } from '~/utils/msrRows'
import { buildReviewQueue, type ReviewEntry } from '~/utils/skewvoirAnalysis/gallery'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const { msrImageUrl } = useMsrFileApi()

// ── SINGLE scope: the review queue ───────────────────────────────────────────
const queue = computed(() =>
  buildReviewQueue(
    props.analysis.siteRows.value,
    props.analysis.activeParam.value,
    props.analysis.waferGeo.value,
    { unit: props.analysis.activeUnit.value }
  )
)

const filter = ref<ReviewFilter>({ evidenceOnly: false, imageOnly: false, query: '' })

const filteredEntries = computed<ReviewEntry[]>(() => {
  const q = filter.value.query.trim().toLowerCase()
  return queue.value.entries.filter((e) => {
    if (filter.value.evidenceOnly && !e.evidenceBacked) return false
    if (filter.value.imageOnly && !e.hasImage) return false
    if (q && !(`${e.chip} ${e.sequence} ${e.mp}`.toLowerCase().includes(q))) return false
    return true
  })
})

const filterCounts = computed(() => ({
  total: queue.value.counts.total,
  shown: filteredEntries.value.length,
  failure: queue.value.counts.failure,
  residual: queue.value.counts.residual,
  monitor: queue.value.counts.monitor
}))

const frameMeta = computed(() => {
  if (props.analysis.scope.value === 'single') {
    const c = queue.value.counts
    return `${c.total} sites · 근거 ${c.evidenceBacked} · MP: ${props.analysis.activeParam.value}`
  }
  return `${images.value.length} sites · MP: ${props.analysis.activeParam.value}`
})

// ── Viewer + drawer state ────────────────────────────────────────────────────
const viewerOpen = ref(false)
const viewerIndex = ref(0)
const drawerOpen = ref(false)
const drawerEntry = ref<ReviewEntry | null>(null)

const openViewer = (entry: ReviewEntry) => {
  const idx = filteredEntries.value.findIndex(e => e.chip === entry.chip && e.sequence === entry.sequence)
  viewerIndex.value = idx >= 0 ? idx : 0
  viewerOpen.value = true
}

// Clicking a card/site links map/table/gallery via the shared focused site.
const focusSite = (entry: ReviewEntry) => {
  props.analysis.setFocusedSite(entry.chip)
  props.analysis.setFocusedSequence(entry.sequence)
}

const onMoveToSite = (chip: string) => {
  const entry = filteredEntries.value.find(e => e.chip === chip)
  props.analysis.setFocusedSite(chip)
  if (entry) props.analysis.setFocusedSequence(entry.sequence)
}

const onEvidence = (entry: ReviewEntry) => {
  drawerEntry.value = entry
  drawerOpen.value = true
}

// ── SET scope: existing filename grid (unchanged behaviour) ──────────────────
const images = computed(() => {
  const seen = new Set<string>()
  const out: { name: string, chip: string, cd: number }[] = []
  for (const r of measuredRows(props.analysis.siteRows.value)) {
    if (r.parameter !== props.analysis.activeParam.value) continue
    const name = r.mp_image_name_01
    if (name && !seen.has(name)) {
      seen.add(name)
      out.push({ name, chip: r.chip_number, cd: r.cd_value })
    }
  }
  return out
})
</script>
