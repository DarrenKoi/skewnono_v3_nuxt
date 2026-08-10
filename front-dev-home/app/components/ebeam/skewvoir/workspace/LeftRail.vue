<template>
  <aside class="flex w-60 shrink-0 flex-col gap-5 overflow-y-auto border-r border-(--sk-border) bg-(--sk-surface) px-3 py-4">
    <!-- View modes — the back-to-search escape hatch sits directly above them and
         is the only saturated control here, so it never reads as a view mode. -->
    <section>
      <UButton
        block
        variant="solid"
        icon="i-lucide-arrow-left"
        label="검색으로"
        size="sm"
        class="mb-3 justify-start bg-(--sk-accent) font-semibold text-white shadow-sm ring-1 ring-(--sk-accent-border) hover:bg-(--sk-accent) hover:brightness-110 focus-visible:outline-(--sk-accent)"
        @click="ws.goSearch()"
      />
      <p class="mb-2 px-1 sk-eyebrow">
        WORKSPACE
      </p>
      <ul class="space-y-1">
        <li
          v-for="mode in ws.viewModes"
          :key="mode.kind"
        >
          <button
            type="button"
            class="flex w-full items-center gap-2.5 rounded-(--sk-r-nav) px-2.5 py-2 text-left transition-colors"
            :class="mode.kind === ws.activeKind.value
              ? 'bg-(--sk-ink) text-(--sk-ink-fg)'
              : 'text-zinc-600 hover:bg-zinc-500/10 dark:text-zinc-300'"
            @click="ws.openView(mode.kind)"
          >
            <span
              class="flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border"
              :class="mode.kind === ws.activeKind.value
                ? 'border-(--sk-ink-fg)/40 bg-(--sk-ink-fg)/15'
                : 'border-zinc-300 dark:border-zinc-600'"
            >
              <UIcon
                v-if="mode.kind === ws.activeKind.value"
                name="i-lucide-check"
                class="h-3 w-3"
              />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[12.5px] font-semibold">{{ mode.label }}</span>
              <span
                class="block truncate text-[11px]"
                :class="mode.kind === ws.activeKind.value ? 'text-(--sk-ink-fg)/70' : 'text-(--sk-ink-muted)'"
              >{{ mode.sub }}</span>
            </span>
            <UKbd
              :value="String(mode.index)"
              size="sm"
              :class="mode.kind === ws.activeKind.value ? 'opacity-80' : 'opacity-60'"
            />
          </button>
        </li>
      </ul>
    </section>

    <!-- CURRENT SELECTION — scope, compact meta/counts, and the member list.
         Row click focuses an MSR (all views); the leading checkbox removes it
         from the compared set (the focused MSR is guarded, never removable).
         Enlarge (⤢) opens the full-detail modal; 분석 준비 상태 opens the readiness modal. -->
    <section
      v-if="ws.selection.value"
      class="space-y-2 border-t border-(--sk-border-soft) pt-4"
    >
      <p class="mb-2 px-1 sk-eyebrow">
        SELECTION
      </p>
      <div class="flex items-center justify-between gap-2 px-1">
        <span
          class="inline-flex items-center gap-1 rounded-(--sk-r-chip) px-1.5 py-0.5 text-[10.5px] font-semibold"
          :class="isSet
            ? 'bg-(--sk-accent-soft) text-(--sk-accent)'
            : 'bg-(--sk-chip-bg) text-(--sk-ink-muted)'"
        >
          <UIcon
            :name="isSet ? 'i-lucide-layers' : 'i-lucide-focus'"
            class="h-3 w-3"
          />
          {{ isSet ? '세트 비교' : '단일 측정' }}
        </span>
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          icon="i-lucide-maximize-2"
          aria-label="상세 보기"
          @click="detailOpen = true"
        />
      </div>

      <!-- Compact meta -->
      <dl class="space-y-1 px-1 text-[12px]">
        <div class="flex items-baseline justify-between gap-2">
          <dt class="sk-label">
            Focus
          </dt>
          <dd class="truncate font-mono font-semibold text-(--sk-ink)">
            {{ focusMsr || '—' }}
          </dd>
        </div>
        <div class="flex items-baseline justify-between gap-2">
          <dt class="sk-label">
            Param
          </dt>
          <dd class="truncate font-mono text-(--sk-ink)">
            {{ analysis.activeParamLabel.value }}
          </dd>
        </div>
        <div class="flex items-baseline justify-between gap-2">
          <dt class="sk-label">
            Lot
          </dt>
          <dd class="truncate font-mono text-(--sk-ink)">
            {{ ws.selection.value.lot || '—' }}
          </dd>
        </div>
      </dl>

      <!-- Compact counts -->
      <div class="flex flex-wrap items-center gap-1 px-1">
        <span class="rounded-(--sk-r-chip) bg-(--sk-ok-soft) px-1.5 py-0.5 font-mono text-[10.5px] text-(--sk-ok)">호환 {{ counts.compatible }}</span>
        <span
          v-if="counts.excluded > 0"
          class="rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-1.5 py-0.5 font-mono text-[10.5px] text-(--sk-bad)"
        >제외 {{ counts.excluded }}</span>
      </div>

      <!-- MSR member list — row = focus, checkbox = membership (guarded) -->
      <template v-if="isSet">
        <div class="flex items-center justify-between px-1">
          <span class="sk-eyebrow">비교 세트 · {{ setChips.length }}</span>
          <button
            type="button"
            class="text-[11px] text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
            @click="deselectToFocus"
          >
            선택 해제
          </button>
        </div>
        <ul class="space-y-1">
          <li
            v-for="chip in setChips"
            :key="chip.msr"
            class="flex items-center gap-1.5"
          >
            <UCheckbox
              :model-value="true"
              :disabled="chip.active"
              :aria-label="`${chip.label} 세트에서 제거`"
              size="sm"
              @update:model-value="removeMember(chip.msr)"
            />
            <button
              type="button"
              class="flex min-w-0 flex-1 items-center gap-2 rounded-(--sk-r-nav) px-2 py-1.5 text-left font-mono text-[12px] transition-colors"
              :class="chip.active
                ? 'bg-(--sk-brand) font-semibold text-(--sk-brand-fg)'
                : 'text-(--sk-ink-muted) hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)'"
              :aria-pressed="chip.active"
              :title="chip.label"
              @click="props.analysis.setFocusedMsr(chip.msr)"
            >
              <UIcon
                :name="chip.active ? 'i-lucide-crosshair' : 'i-lucide-circle-dot'"
                class="h-3.5 w-3.5 shrink-0"
              />
              <span class="min-w-0 flex-1 truncate">{{ chip.label }}</span>
            </button>
          </li>
        </ul>
      </template>

      <!-- Readiness modal opener -->
      <UButton
        block
        color="neutral"
        variant="soft"
        size="xs"
        class="justify-start"
        icon="i-lucide-list-checks"
        :label="`분석 준비 상태${counts.excluded > 0 ? ` · 제외 ${counts.excluded}` : ''}`"
        @click="emit('openReadiness')"
      />
    </section>

    <!-- Full-detail enlarge modal -->
    <EbeamSkewvoirWorkspaceSelectionDetailModal
      v-if="ws.selection.value"
      v-model:open="detailOpen"
      :ws="ws"
      :analysis="analysis"
    />

    <!-- Actions — separated from the selection above by its own bordered section -->
    <section
      v-if="ws.selection.value"
      class="border-t border-(--sk-border) pt-4"
    >
      <p class="mb-2 px-1 sk-eyebrow">
        ACTIONS
      </p>
      <div class="space-y-1.5">
        <UButton
          v-for="action in actions"
          :key="action.label"
          block
          color="neutral"
          variant="ghost"
          size="sm"
          class="justify-start"
          :icon="action.icon"
          :label="action.label"
          @click="action.onClick()"
        />
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { copyTextToClipboard } from '~/utils/csvDownload'
import { recipeDetailRoute } from '~/utils/recipeView'
import { removeFromSet, clearToFocus } from '~/utils/skewvoirAnalysis/setEditing'
import { formatSelectionSummary } from '~/utils/skewvoirAnalysis/summary'

const props = defineProps<{ ws: SkewvoirWorkspace, analysis: SkewvoirAnalysis, fab: string }>()

const emit = defineEmits<{ openReadiness: [] }>()

const detailOpen = ref(false)

// In a comparison set (scope=set) the rail shows the 비교 세트 members as the
// focus switcher (works on every view); a single measurement keeps the plain
// CURRENT SELECTION card.
const isSet = computed(() => props.analysis.scope.value === 'set' && props.analysis.msrList.value.length >= 2)
const setChips = computed(() =>
  props.analysis.msrList.value.map(msr => ({
    msr,
    label: props.analysis.msrLabel(msr),
    active: msr === props.analysis.focusMsr.value
  }))
)

const focusMsr = computed(() => props.ws.selection.value?.msr ?? '')
const counts = computed(() => props.analysis.manifest.value.counts)

// Uncheck removes the member (focused MSR is guarded inside removeFromSet).
const removeMember = (msr: string) => {
  props.ws.setMsrs(removeFromSet(props.analysis.msrList.value, msr, focusMsr.value))
}

// 선택 해제 — empty the set down to the focused MSR.
const deselectToFocus = () => {
  if (focusMsr.value) props.ws.setMsrs(clearToFocus(focusMsr.value))
}

const toast = useToast()
const router = useRouter()

// Open the current measurement's recipe in the existing "Recipe 열어 보기" page,
// in a new tab. The analysis route isn't fab-scoped, so the fab comes from the
// focus measurement (passed in).
const openRecipe = () => {
  const recipe = props.ws.selection.value?.recipe
  if (!recipe || !props.fab) return
  const route = recipeDetailRoute(props.ws.toolType, props.fab, 'open', recipe, 'redis', props.fab)
  window.open(router.resolve(route).href, '_blank', 'noopener')
}

// What we copy is a share URL (or a summary carrying one), and its msr ids
// — `20260509_ADI_CD_BIAS_ABC123_STD_00001_KPB266344_ECDX285` — offer the
// browser no break opportunity, so the default toast runs them past its right
// edge and silently clips the middle of the link. break-all, same as the msr id
// in ReadinessModal. This matters most on the failure path below, where the
// toast body IS the copy-it-yourself fallback.
const copyToastUi = { description: 'break-all' }

// copyTextToClipboard, not navigator.clipboard: the Clipboard API is
// secure-context only and production is served over plain http://, where
// `navigator.clipboard` is undefined. The util carries the execCommand
// fallback that keeps this working there.
const copyToClipboard = async (text: string, okTitle: string) => {
  if (await copyTextToClipboard(text)) {
    toast.add({ title: okTitle, description: text, icon: 'i-lucide-clipboard-check', color: 'success', ui: copyToastUi })
  } else {
    toast.add({ title: '복사하지 못했습니다', description: text, icon: 'i-lucide-triangle-alert', color: 'warning', ui: copyToastUi })
  }
}

const share = () => copyToClipboard(props.ws.shareUrl(), '링크가 복사되었습니다')

// Selection facts as paste-ready text (messenger / report hand-off).
const copySummary = () => {
  const sel = props.ws.selection.value
  if (!sel) return
  copyToClipboard(
    formatSelectionSummary(sel, props.analysis.activeParamLabel.value, props.ws.shareUrl()),
    '요약이 복사되었습니다'
  )
}

// Excel export lives on the data table, not here. Annotation (per-MSR triage
// notes) is tracked in .scratch/skewvoir-annotation/ — no UI until it works.
const actions = [
  { label: '요약 복사', icon: 'i-lucide-clipboard-list', onClick: copySummary },
  { label: 'Recipe 열어보기', icon: 'i-lucide-file-search', onClick: openRecipe },
  { label: 'Share', icon: 'i-lucide-share-2', onClick: share }
]
</script>
