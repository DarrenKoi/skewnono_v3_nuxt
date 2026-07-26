<template>
  <UModal
    v-model:open="open"
    :title="scope === 'set' ? '세트 비교 · 상세' : '단일 측정 · 상세'"
    :ui="{ content: 'w-[92vw] sm:max-w-3xl' }"
  >
    <template #body>
      <div
        v-if="ws.selection.value"
        class="flex flex-col gap-4"
      >
        <!-- Scope + Focus + Parameter -->
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
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
          <span class="flex items-baseline gap-1.5">
            <span class="sk-label">Focus</span>
            <span class="truncate font-mono text-[12px] font-semibold text-(--sk-ink)">{{ ws.selection.value.msr || '—' }}</span>
          </span>
          <span class="flex items-baseline gap-1.5">
            <span class="sk-label">Parameter</span>
            <span class="font-mono text-[12px] text-(--sk-ink)">{{ analysis.activeParamLabel.value || '—' }}</span>
          </span>
        </div>

        <!-- Full selection fields -->
        <dl class="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]">
          <div
            v-for="field in selectionFields"
            :key="field.label"
            class="flex items-baseline justify-between gap-2"
          >
            <dt class="sk-label">
              {{ field.label }}
            </dt>
            <dd
              class="truncate font-mono text-(--sk-ink)"
              :class="{ 'font-semibold': field.strong }"
            >
              {{ field.value }}
            </dd>
          </div>
        </dl>

        <!-- Counts -->
        <div class="flex flex-wrap items-center gap-1.5 border-t border-(--sk-border-soft) pt-3">
          <span class="rounded-(--sk-r-chip) bg-(--sk-ok-soft) px-2 py-0.5 font-mono text-[11px] text-(--sk-ok)">호환 {{ counts.compatible }}</span>
          <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 font-mono text-[11px] text-(--sk-ink-muted)">로드 {{ counts.loaded }}</span>
          <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-0.5 font-mono text-[11px] text-(--sk-ink-muted)">선택 {{ counts.selected }}</span>
          <span
            v-if="counts.excluded > 0"
            class="rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-2 py-0.5 font-mono text-[11px] text-(--sk-bad)"
          >제외 {{ counts.excluded }}</span>
        </div>

        <!-- Reference provenance -->
        <div
          v-if="referenceLabel"
          class="flex items-baseline gap-1.5"
        >
          <span class="sk-label shrink-0">기준</span>
          <span class="truncate font-mono text-[11px] text-(--sk-ink-muted)">{{ referenceLabel }}</span>
        </div>

        <!-- Searchable set editor (set scope only) — the place to add a new MSR -->
        <div
          v-if="scope === 'set'"
          class="flex flex-col gap-1.5 border-t border-(--sk-border-soft) pt-3"
        >
          <span class="sk-label">세트 편집</span>
          <USelectMenu
            :model-value="ws.msrList.value"
            multiple
            value-key="value"
            :items="candidateItems"
            :search-input="{ placeholder: 'lot / eq 로 검색…' }"
            placeholder="측정 추가/제거"
            size="sm"
            @update:model-value="onEditSet"
          />
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { formatRecipeTimestamp } from '~/utils/recipeView'
import { ensureFocus } from '~/utils/skewvoirAnalysis/setEditing'

const props = defineProps<{ ws: SkewvoirWorkspace, analysis: SkewvoirAnalysis }>()
const open = defineModel<boolean>('open', { default: false })

const onEditSet = (list: string[]) => {
  props.ws.setMsrs(ensureFocus(list, props.ws.selection.value?.msr ?? ''))
}

const scope = computed(() => props.analysis.scope.value)
const counts = computed(() => props.analysis.manifest.value.counts)

const selectionFields = computed(() => {
  const sel = props.ws.selection.value
  if (!sel) return []
  return [
    { label: 'Lot', value: sel.lot, strong: true },
    { label: 'Recipe', value: sel.recipe, strong: false },
    { label: 'EQ', value: sel.eq, strong: false },
    { label: 'MP', value: sel.mp, strong: false },
    { label: 'Captured', value: sel.capturedAt, strong: false }
  ]
})

const referenceLabel = computed(() => {
  const ref = props.analysis.reference.value
  if (!ref) return ''
  const recipe = ref.signature.recipe.state === 'known'
    ? ref.signature.recipe.value.recipeName
    : null
  return recipe ? `${ref.msr} · ${recipe}` : ref.msr
})

const candidateItems = computed(() =>
  props.analysis.candidateRows.value.map(r => ({
    label: `${formatRecipeTimestamp(r.timestamp)} · ${r.eqp_id} · ${r.lot_id}`,
    value: r.msr
  }))
)
</script>
