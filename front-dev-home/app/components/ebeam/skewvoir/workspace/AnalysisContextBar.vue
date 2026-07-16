<template>
  <div
    v-if="ws.selection.value"
    class="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-(--sk-border) bg-(--sk-surface) px-3 py-2"
  >
    <!-- Scope -->
    <span
      class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) px-2 py-0.5 text-[11px] font-semibold"
      :class="scope === 'set'
        ? 'bg-(--sk-accent-soft) text-(--sk-accent)'
        : 'bg-(--sk-chip-bg) text-(--sk-ink-muted)'"
    >
      <UIcon
        :name="scope === 'set' ? 'i-lucide-layers' : 'i-lucide-focus'"
        class="h-3.5 w-3.5"
      />
      {{ scope === 'set' ? '세트 비교' : '단일 측정' }}
    </span>

    <!-- Focus MSR -->
    <span class="flex items-baseline gap-1.5">
      <span class="sk-label">Focus</span>
      <span class="truncate font-mono text-[12px] font-semibold text-(--sk-ink)">
        {{ focusMsr || '—' }}
      </span>
    </span>

    <!-- Active parameter -->
    <span class="flex items-baseline gap-1.5">
      <span class="sk-label">Parameter</span>
      <span class="font-mono text-[12px] text-(--sk-ink)">
        {{ analysis.activeParam.value || '—' }}
      </span>
    </span>

    <!-- Compatible / excluded counts -->
    <span class="flex items-center gap-1.5">
      <span
        class="rounded-(--sk-r-chip) bg-(--sk-ok-soft) px-2 py-0.5 font-mono text-[11px] text-(--sk-ok)"
        :title="`호환 ${counts.compatible} / 로드 ${counts.loaded} / 선택 ${counts.selected}`"
      >
        호환 {{ counts.compatible }}
      </span>
      <span
        v-if="counts.excluded > 0"
        class="rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-2 py-0.5 font-mono text-[11px] text-(--sk-bad)"
        title="기준과 호환되지 않아 제외된 측정"
      >
        제외 {{ counts.excluded }}
      </span>
    </span>

    <!-- Reference provenance -->
    <span
      v-if="referenceLabel"
      class="flex items-baseline gap-1.5"
    >
      <span class="sk-label">기준</span>
      <span class="truncate font-mono text-[11px] text-(--sk-ink-muted)">
        {{ referenceLabel }}
      </span>
    </span>

    <!-- Set editor — writes straight to the URL ?msrs= (shared across set views) -->
    <div
      v-if="scope === 'set'"
      class="flex min-w-[16rem] flex-1 items-center gap-2"
    >
      <span class="sk-label shrink-0">비교 세트</span>
      <USelectMenu
        :model-value="ws.msrList.value"
        multiple
        value-key="value"
        :items="candidateItems"
        :search-input="{ placeholder: 'lot / eq 로 검색…' }"
        placeholder="측정 추가/제거"
        class="min-w-[12rem] flex-1"
        size="xs"
        @update:model-value="ws.setMsrs"
      />
    </div>

    <!-- Readiness drawer opener -->
    <UButton
      class="ml-auto shrink-0"
      color="neutral"
      variant="ghost"
      size="xs"
      icon="i-lucide-list-checks"
      :label="`분석 준비 상태${counts.excluded > 0 ? ` · 제외 ${counts.excluded}` : ''}`"
      @click="emit('openReadiness')"
    />
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { formatRecipeTimestamp } from '~/utils/recipeView'

const props = defineProps<{
  ws: SkewvoirWorkspace
  analysis: SkewvoirAnalysis
}>()

const emit = defineEmits<{ openReadiness: [] }>()

const scope = computed(() => props.analysis.scope.value)
const focusMsr = computed(() => props.ws.selection.value?.msr ?? '')
const counts = computed(() => props.analysis.manifest.value.counts)

// Reference provenance — the focus MSR and its recipe identity, when known.
const referenceLabel = computed(() => {
  const ref = props.analysis.reference.value
  if (!ref) return ''
  const recipe = ref.signature.recipe.state === 'known'
    ? ref.signature.recipe.value.recipeName
    : null
  return recipe ? `${ref.msr} · ${recipe}` : ref.msr
})

// Candidate pool for the set editor (mirrors the Time-Series picker labels).
const candidateItems = computed(() =>
  props.analysis.candidateRows.value.map(r => ({
    label: `${formatRecipeTimestamp(r.timestamp)} · ${r.eqp_id} · ${r.lot_id}`,
    value: r.msr
  }))
)
</script>
