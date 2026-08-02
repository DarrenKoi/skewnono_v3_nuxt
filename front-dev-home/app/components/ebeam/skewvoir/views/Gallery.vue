<template>
  <EbeamSkewvoirPanelFrame
    class="h-full min-h-0"
    body-class="flex min-h-0 flex-col overflow-hidden"
    title="SEM Gallery"
    :meta="frameMeta"
    icon="i-lucide-images"
  >
    <!-- Loading -->
    <AppLoadingState
      v-if="analysis.focusPending.value"
      variant="inline"
      class="h-96"
      title="불러오는 중입니다."
    />

    <!-- ── SINGLE scope: priority visual-evidence review queue ─────────────── -->
    <div
      v-else-if="analysis.scope.value === 'single'"
      class="flex min-h-0 flex-1 flex-col gap-3"
    >
      <EbeamSkewvoirGalleryReviewFilters
        :model-value="filter"
        :counts="filterCounts"
        @update:model-value="onFilterUpdate"
      />

      <p
        v-if="queue.readiness.residual !== 'ok'"
        class="rounded-(--sk-r-nav) border border-(--sk-border-soft) bg-(--sk-chip-bg)/40 px-3 py-2 sk-meta"
      >
        {{ queue.readiness.reason }}
      </p>

      <div
        v-if="filteredEntries.length"
        class="grid min-h-0 flex-1 auto-rows-max grid-cols-2 content-start gap-2 overflow-auto sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
      >
        <EbeamSkewvoirGalleryEvidenceCard
          v-for="entry in filteredEntries"
          :key="`${entry.chip}#${entry.sequence}`"
          :entry="entry"
          :src="entry.image && focusCtx.eqp_ip ? imageUrl(focusCtx.eqp_ip, focusCtx.class_name, focusCtx.msr, entry.image) : null"
          :focused="entry.chip === analysis.focusedSite.value"
          @open="openViewer(entry)"
          @focus="focusSite(entry)"
        />
      </div>
      <div
        v-else
        class="flex h-72 items-center justify-center sk-body"
      >
        {{ queue.entries.length ? '필터에 해당하는 항목이 없습니다.' : `${analysis.activeParamLabel.value} 근거 항목이 없습니다.` }}
      </div>
    </div>

    <!-- ── SET scope: existing focus-only filename grid (Task 12 replaces) ──── -->
    <div
      v-else-if="images.length"
      class="grid min-h-0 flex-1 auto-rows-max grid-cols-3 content-start gap-2 overflow-auto sm:grid-cols-4 xl:grid-cols-6"
    >
      <figure
        v-for="img in images"
        :key="img.name"
        class="overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
      >
        <!-- TIFF originals can't render in <img>; offer the download instead. -->
        <a
          v-if="isTiffName(img.name)"
          :href="focusCtx.eqp_ip ? imageUrl(focusCtx.eqp_ip, focusCtx.class_name, focusCtx.msr, img.name) : undefined"
          :download="img.name"
          class="flex aspect-square w-full flex-col items-center justify-center gap-1 bg-(--sk-chip-bg) text-center"
        >
          <UIcon
            name="i-lucide-file-image"
            class="h-5 w-5 text-(--sk-ink-subtle)"
          />
          <span class="sk-meta">TIFF · 다운로드</span>
        </a>
        <img
          v-else
          :src="focusCtx.eqp_ip ? imageUrl(focusCtx.eqp_ip, focusCtx.class_name, focusCtx.msr, img.name) : undefined"
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
      {{ analysis.activeParamLabel.value }} 이미지가 없습니다.
    </div>

    <!-- Enlarged viewer + measurement-evidence drawer (single scope). -->
    <EbeamSkewvoirGalleryImageViewer
      :open="viewerOpen"
      :entries="filteredEntries"
      :index="viewerIndex"
      :geo="analysis.waferGeo.value"
      :eqp_ip="focusCtx.eqp_ip"
      :class_name="focusCtx.class_name"
      :msr="focusCtx.msr"
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
import { isTiffName } from '~/utils/imageKind'
import { measuredRows } from '~/utils/msrRows'
import { buildReviewQueue, resolveEvidenceOnly, type ReviewEntry } from '~/utils/skewvoirAnalysis/gallery'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const { imageUrl } = useMsrImageApi()

// Every image in this single-scope gallery belongs to the FOCUS MSR, so its
// image-API context is the focus row's eqp_ip/class_name + the focus msr id.
// Empty strings (never undefined) when the focus row hasn't resolved yet —
// callers gate on `focusCtx.eqp_ip` before building a URL/job.
const focusCtx = useFocusImageCtx(props.analysis)

// ── SINGLE scope: the review queue ───────────────────────────────────────────
const queue = computed(() =>
  buildReviewQueue(
    props.analysis.siteRows.value,
    props.analysis.activeParam.value,
    props.analysis.waferGeo.value,
    { unit: props.analysis.activeUnit.value }
  )
)

// The reviewer's EXPLICIT 이상·실패 우선 choice, seeded from the URL `filter`
// key; null = untouched, which hands the decision to resolveEvidenceOnly's
// pre-armed default. Both values round-trip, so an absent key means "default"
// rather than "off" — that distinction is what lets the default arm the toggle
// while a link shared with it deliberately off still reopens off.
const evidenceOnlyChoice = ref<boolean | null>(
  props.analysis.filterParam.value === 'priority'
    ? true
    : props.analysis.filterParam.value === 'all' ? false : null
)

// PRE-ARMED unless the reviewer says otherwise — see resolveEvidenceOnly. This
// reads the live queue rather than a setup-time snapshot because siteRows arrive
// async: a seed taken during setup would always see 0 evidence and never arm.
const evidenceOnly = computed(() =>
  resolveEvidenceOnly(evidenceOnlyChoice.value, queue.value.counts.evidenceBacked)
)
const imageOnly = ref(false)
const searchQuery = ref('')

const filter = computed<ReviewFilter>(() => ({
  evidenceOnly: evidenceOnly.value,
  imageOnly: imageOnly.value,
  query: searchQuery.value
}))

// ReviewFilters emits the whole filter object; split it back into the pieces
// that own their state. Touching 이상·실패 우선 records an explicit choice, so
// the pre-armed default stops applying from then on.
const onFilterUpdate = (next: ReviewFilter) => {
  if (next.evidenceOnly !== evidenceOnly.value) evidenceOnlyChoice.value = next.evidenceOnly
  imageOnly.value = next.imageOnly
  searchQuery.value = next.query
}

// Write the reviewer's choice back to the URL so a filtered queue is shareable.
// Only this toggle round-trips through `filter`; image-only/text search stay
// local-only, unchanged.
watch(evidenceOnlyChoice, (choice) => {
  props.analysis.setFilter(choice == null ? null : choice ? 'priority' : 'all')
})

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
    return `${c.total} sites · 근거 ${c.evidenceBacked} · MP: ${props.analysis.activeParamLabel.value}`
  }
  return `${images.value.length} sites · MP: ${props.analysis.activeParamLabel.value}`
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
