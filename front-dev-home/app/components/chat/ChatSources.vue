<script setup lang="ts">
import type { SourceRef } from '~/composables/useChatApi'
import { figureUrl, formatSourceLabel } from '~/utils/chatSources'

defineProps<{ sources: SourceRef[] }>()

const config = useRuntimeConfig()
const srcFor = (figureId: string) => figureUrl(config.public.apiBase, figureId)

/**
 * Figures whose image did not load, keyed by figure_id.
 *
 * A citation can carry a figure_id with nothing stored behind it — a manual
 * indexed without figure extraction, or a deployment with no figure store at
 * all — and the route answers 404 for each of those cases alike. A missing
 * image is therefore an ordinary state rather than something to report: the
 * citation falls back to the plain chip it was before figures existed.
 */
const failed = ref(new Set<string>())
const markFailed = (figureId: string) => {
  failed.value = new Set(failed.value).add(figureId)
}
const hasFigure = (source: SourceRef): source is SourceRef & { figure_id: string } =>
  !!source.figure_id && !failed.value.has(source.figure_id)

const zoomedSource = ref<SourceRef | null>(null)
const isOpen = computed({
  get: () => zoomedSource.value !== null,
  set: (value: boolean) => {
    if (!value) zoomedSource.value = null
  }
})

// Zoom is a two-step toggle rather than a continuous control: the figure is
// either fitted to the dialog or magnified enough to read a callout label,
// and every value between those is a scroll position the user has to undo.
const isMagnified = ref(false)
watch(zoomedSource, () => {
  isMagnified.value = false
})
</script>

<template>
  <section
    v-if="sources.length"
    class="sk-chat-sources"
    aria-label="참고 출처"
  >
    <span class="sk-chat-sources-label">출처</span>
    <ul class="sk-chat-source-list">
      <li
        v-for="source in sources"
        :key="source.source_id"
      >
        <!-- Source locators are internal identifiers, not navigable URLs, so
             only a figure-bearing citation is actionable at all. -->
        <button
          v-if="hasFigure(source)"
          type="button"
          class="sk-chat-source-chip sk-chat-source-chip-figure"
          :title="source.snippet"
          :aria-label="`${formatSourceLabel(source)} 그림 크게 보기`"
          @click="zoomedSource = source"
        >
          <img
            :src="srcFor(source.figure_id)"
            alt=""
            loading="lazy"
            decoding="async"
            class="sk-chat-source-thumb"
            @error="markFailed(source.figure_id)"
          >
          {{ formatSourceLabel(source) }}
          <UIcon
            name="i-lucide-maximize-2"
            class="sk-chat-source-zoom"
            aria-hidden="true"
          />
        </button>
        <span
          v-else
          class="sk-chat-source-chip"
          :title="source.snippet"
        >
          <UIcon
            name="i-lucide-file-text"
            aria-hidden="true"
          />
          {{ formatSourceLabel(source) }}
        </span>
      </li>
    </ul>

    <UModal
      v-model:open="isOpen"
      :title="zoomedSource ? formatSourceLabel(zoomedSource) : ''"
      :ui="{ content: 'w-[92vw] sm:max-w-[900px]' }"
    >
      <template #body>
        <div
          v-if="zoomedSource?.figure_id"
          class="sk-chat-figure-stage"
          :class="{ 'sk-chat-figure-stage-magnified': isMagnified }"
        >
          <!-- No `loading="lazy"`: the user has already asked for this one. -->
          <img
            :src="srcFor(zoomedSource.figure_id)"
            :alt="`${formatSourceLabel(zoomedSource)} 그림`"
            decoding="async"
            class="sk-chat-figure"
            :class="{ 'sk-chat-figure-magnified': isMagnified }"
            @click="isMagnified = !isMagnified"
          >
        </div>
        <p
          v-if="zoomedSource?.snippet"
          class="sk-chat-figure-snippet"
        >
          {{ zoomedSource.snippet }}
        </p>
      </template>
    </UModal>
  </section>
</template>

<style scoped>
.sk-chat-sources {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-top: 0.625rem;
}

.sk-chat-sources-label {
  flex-shrink: 0;
  padding-top: 0.2rem;
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--sk-ink-subtle);
}

.sk-chat-source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.sk-chat-source-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  max-width: 100%;
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--sk-border-soft);
  border-radius: 999px;
  background: var(--sk-muted-surface);
  color: var(--sk-ink-muted);
  font-size: 0.6875rem;
  line-height: 1.35;
}

.sk-chat-source-chip svg {
  flex-shrink: 0;
}

/* The one actionable chip in the row, so it carries the affordance the
   others deliberately lack. */
.sk-chat-source-chip-figure {
  padding-left: 0.2rem;
  cursor: pointer;
  transition: border-color 200ms, color 200ms;
}

.sk-chat-source-chip-figure:hover {
  border-color: var(--sk-border);
  color: var(--sk-ink);
}

.sk-chat-source-thumb {
  flex-shrink: 0;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 999px;
  object-fit: cover;
  background: var(--sk-muted-surface);
}

.sk-chat-source-zoom {
  flex-shrink: 0;
  width: 0.6875rem;
  height: 0.6875rem;
  color: var(--sk-ink-subtle);
}

.sk-chat-figure-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  max-height: 70vh;
  overflow: hidden;
  border: 1px solid var(--sk-border-soft);
  border-radius: var(--sk-r-card);
  /* Manual figures are line art and photographs off a printed page, not SEM
     micrographs — so this is a normal inverting surface, not the Dark Field
     canvas, whose scope is the simulated imagery only (DESIGN.md §Colors). */
  background: var(--sk-muted-surface);
}

.sk-chat-figure-stage-magnified {
  overflow: auto;
}

.sk-chat-figure {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  cursor: zoom-in;
  transition: transform 200ms;
}

.sk-chat-figure-magnified {
  max-width: none;
  max-height: none;
  transform: scale(2);
  transform-origin: center center;
  cursor: zoom-out;
}

.sk-chat-figure-snippet {
  margin-top: 0.75rem;
  color: var(--sk-ink-muted);
  font-size: 0.75rem;
  line-height: 1.6;
}
</style>
