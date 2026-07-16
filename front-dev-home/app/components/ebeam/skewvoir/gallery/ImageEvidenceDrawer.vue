<template>
  <USlideover
    :open="open"
    title="측정 근거 레이어"
    :description="entry ? `${entry.chip} · seq ${entry.sequence}` : '이미지 측정 근거'"
    :ui="{ content: 'w-[92vw] sm:max-w-[400px]' }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div
        v-if="entry"
        class="space-y-5"
      >
        <!-- Measurement-evidence capability: Phase-1 backend provides no ROI /
             edge / CD gauge / line profile / algorithm version, so that layer is
             HIDDEN and disclosed rather than faked. -->
        <section>
          <p class="mb-2 sk-eyebrow">
            측정 근거 레이어
          </p>
          <div class="flex items-start gap-2 rounded-(--sk-r-nav) border border-dashed border-(--sk-border) px-3 py-2.5">
            <UIcon
              name="i-lucide-info"
              class="mt-0.5 h-4 w-4 shrink-0 text-(--sk-ink-subtle)"
            />
            <div class="space-y-1">
              <p class="sk-body">
                원본 image만 제공됨
              </p>
              <p class="sk-meta">
                ROI·엣지·CD 게이지·라인 프로파일·알고리즘 버전은 Phase-1 backend에서 제공되지 않습니다.
              </p>
            </div>
          </div>
        </section>

        <!-- Artifact-suspicion review tags — a SEPARATE axis from any pattern
             verdict; reviewer-selected, not machine-classified. -->
        <section>
          <p class="mb-2 sk-eyebrow">
            artifact 의심 (검토 태그)
          </p>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="tag in ARTIFACT_TAGS"
              :key="tag.key"
              type="button"
              class="rounded-(--sk-r-chip) border px-2 py-1 font-mono text-[11px] transition-colors duration-200"
              :class="selected.has(tag.key)
                ? 'border-(--sk-warn)/50 bg-(--sk-warn)/10 text-(--sk-warn)'
                : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="toggle(tag.key)"
            >
              {{ tag.label }}
            </button>
          </div>
          <p class="mt-2 sk-meta">
            태그는 검토용 메모이며 패턴 판정과 무관합니다.
          </p>
        </section>

        <!-- Vendor acquisition-score monitoring — separate from any verdict. -->
        <section v-if="entry.monitor">
          <p class="mb-2 sk-eyebrow">
            취득 점수 모니터링
          </p>
          <div class="space-y-1 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-3 py-2.5">
            <div
              v-for="s in scoreRows"
              :key="s.k"
              class="flex items-center justify-between gap-2 text-[12.5px]"
            >
              <span class="text-(--sk-ink-muted)">{{ s.k }}</span>
              <span class="font-mono tabular-nums text-(--sk-ink)">{{ s.v }}</span>
            </div>
            <p class="pt-1 sk-meta">
              {{ entry.monitor.detail }}
            </p>
          </div>
        </section>
      </div>
      <p
        v-else
        class="sk-body"
      >
        선택된 이미지가 없습니다.
      </p>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import { ARTIFACT_TAGS, type ReviewEntry } from '~/utils/skewvoirAnalysis/gallery'

const props = defineProps<{
  open: boolean
  entry: ReviewEntry | null
}>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

// Reviewer-selected artifact tags, remembered per site key while the drawer lives.
const tagsBySite = ref<Record<string, Set<string>>>({})
const siteKey = computed(() => (props.entry ? `${props.entry.chip}#${props.entry.sequence}` : ''))
const selected = computed(() => tagsBySite.value[siteKey.value] ?? new Set<string>())

const toggle = (key: string) => {
  const set = new Set(selected.value)
  if (set.has(key)) set.delete(key)
  else set.add(key)
  tagsBySite.value = { ...tagsBySite.value, [siteKey.value]: set }
}

const scoreRows = computed(() => {
  const m = props.entry?.monitor
  if (!m) return []
  return [
    { k: '측정 점수', v: m.measurementScore != null ? String(m.measurementScore) : '—' },
    { k: '어드레싱1', v: m.addressing1Score != null ? String(m.addressing1Score) : '—' },
    { k: '어드레싱2', v: m.addressing2Score != null ? String(m.addressing2Score) : '—' }
  ]
})
</script>
