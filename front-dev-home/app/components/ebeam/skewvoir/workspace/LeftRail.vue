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

    <!-- CURRENT SELECTION — scope, the active parameter, counts, and the member
         list. Every measurement is rendered through the SAME two-line shape
         (lot over `eqp · time`), focus included, so the rail states an msr's
         identity exactly one way; the old `Focus` row restated it as a raw msr
         id that the 240px rail truncated to `20260509_EDGE_PROFILE_…`.

         The member list is INERT except on 측정 개요. Every other view draws the
         whole set at once, so singling one member out there answers a question
         nobody asked — and the row that did it sat beside a checkbox that
         silently REMOVED the member, which is how a multi-measurement trend
         used to vanish under a click meant to inspect. Membership is edited in
         one place now: 세트 편집 in the ⤢ modal, which can add as well as
         remove. 측정 개요 renders one measurement by definition, so there the
         rows stay clickable — that is the view's own picker.

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

      <!-- The one fact here that is NOT per-measurement: which parameter every
           chart below is following. Lot and eq moved into the member rows. -->
      <div class="flex items-baseline justify-between gap-2 px-1 text-[12px]">
        <span class="sk-label">Param</span>
        <span class="truncate font-mono text-(--sk-ink)">{{ analysis.activeParamLabel.value }}</span>
      </div>

      <!-- Compact counts -->
      <div class="flex flex-wrap items-center gap-1 px-1">
        <span class="rounded-(--sk-r-chip) bg-(--sk-ok-soft) px-1.5 py-0.5 font-mono text-[10.5px] text-(--sk-ok)">호환 {{ counts.compatible }}</span>
        <span
          v-if="counts.excluded > 0"
          class="rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-1.5 py-0.5 font-mono text-[10.5px] text-(--sk-bad)"
        >제외 {{ counts.excluded }}</span>
      </div>

      <!-- Member list. One markup shape, two behaviours: `is` swaps the row
           between a focus button (측정 개요) and a plain div (everywhere else),
           so the two variants cannot drift apart in type, spacing or truncation
           — the difference between them is exactly the interaction. -->
      <div class="flex items-center justify-between gap-2 px-1">
        <span class="sk-eyebrow">{{ isSet ? `비교 세트 · ${members.length}` : '측정' }}</span>
        <button
          v-if="canSwitchFocus"
          type="button"
          class="text-[11px] text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
          @click="deselectToFocus"
        >
          선택 해제
        </button>
      </div>
      <ul class="space-y-1">
        <li
          v-for="member in members"
          :key="member.msr"
        >
          <component
            :is="canSwitchFocus ? 'button' : 'div'"
            :type="canSwitchFocus ? 'button' : undefined"
            class="flex w-full min-w-0 flex-col gap-0.5 rounded-(--sk-r-nav) px-2 py-1.5 text-left transition-colors"
            :class="canSwitchFocus
              ? (member.active
                ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
                : 'hover:bg-(--sk-chip-bg)')
              : ''"
            :aria-pressed="canSwitchFocus ? member.active : undefined"
            :title="member.title"
            @click="canSwitchFocus && analysis.setFocusedMsr(member.msr)"
          >
            <span
              class="min-w-0 truncate font-mono text-[12px] font-semibold"
              :class="canSwitchFocus && member.active ? '' : 'text-(--sk-ink)'"
            >{{ member.lot }}</span>
            <span
              v-if="member.sub"
              class="min-w-0 truncate font-mono text-[11px]"
              :class="canSwitchFocus && member.active ? 'opacity-80' : 'text-(--sk-ink-muted)'"
            >{{ member.sub }}</span>
          </component>
        </li>
      </ul>

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
import { clearToFocus } from '~/utils/skewvoirAnalysis/setEditing'
import { formatSelectionSummary } from '~/utils/skewvoirAnalysis/summary'

const props = defineProps<{ ws: SkewvoirWorkspace, analysis: SkewvoirAnalysis, fab: string }>()

const emit = defineEmits<{ openReadiness: [] }>()

const detailOpen = ref(false)

// A comparison set (scope=set with 2+ members) vs. a single measurement. Only
// the SECTION HEADINGS differ between the two now — the member rows render the
// same either way, because parseMsrList falls the `msrs` list back to the lone
// focus `msr`, so a single measurement is just a set of one.
const isSet = computed(() => props.analysis.scope.value === 'set' && props.analysis.msrList.value.length >= 2)

// Whether a member row may be clicked to move the focus. Two conditions, and
// both are about there being a choice to make:
//
//   • 측정 개요 — that view renders ONE measurement (wafer map, SEM image and
//     radius plot are all single-msr), so it has to be told which, and this
//     list is its picker. Every other view draws the whole set at once, where
//     picking one member changes nothing but which line is emphasised — at the
//     cost of making a set assembled to be read TOGETHER look like a
//     one-at-a-time list.
//   • a SET — with one measurement there is nothing to switch to, and a lone
//     row rendered as a permanently-pressed toggle offers a choice that isn't.
const canSwitchFocus = computed(() => props.ws.activeKind.value === 'dashboard' && isSet.value)

const focusMsr = computed(() => props.ws.selection.value?.msr ?? '')
const counts = computed(() => props.analysis.manifest.value.counts)

// One shape for every measurement in the rail: `lot` over `eqp · time`.
//
// The meas_hist row is the source. A DEEP-LINKED msr may have no row (the
// analysis route loads a file by msr alone, deliberately, so a shared link
// works before/without its history) — for the focus we then fall back to the
// identity the URL itself carries, which is exactly what those `lot`/`eq`/`cap`
// params exist for. With neither, the raw msr id stands in: unreadable at 240px
// but honest, and the `title` carries it in full for a hover.
const members = computed(() =>
  props.analysis.msrList.value.map((msr) => {
    const row = props.analysis.rowByMsr.value.get(msr)
    const sel = props.ws.selection.value
    const url = sel && sel.msr === msr ? sel : null
    const cap = url?.capturedAt && url.capturedAt !== '—' ? url.capturedAt : ''
    return {
      msr,
      lot: row?.lot_id || url?.lot || msr,
      // msrLabel already reads `eqp · time` off the row; it returns the bare
      // msr id when there is no row, which would restate the line above it.
      sub: row ? props.analysis.msrLabel(msr) : [url?.eq, cap].filter(Boolean).join(' · '),
      title: msr,
      active: msr === focusMsr.value
    }
  })
)

// 선택 해제 — empty the set down to the focused MSR. Offered only where the
// focus is meaningful (측정 개요); membership is otherwise edited in the ⤢
// modal's 세트 편집, which can add as well as remove.
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

// The FAILURE toast is the copy-it-yourself fallback, so it has to carry the
// whole text — and msr ids like `20260509_ADI_CD_BIAS_ABC123_STD_00001_
// KPB266344_ECDX285` offer the browser no break opportunity, so without
// break-all the toast runs them past its right edge and silently clips the
// middle. Same treatment as the msr id in ReadinessModal.
const copyToastUi = { description: 'break-all' }

// copyTextToClipboard, not navigator.clipboard: the Clipboard API is
// secure-context only and production is served over plain http://, where
// `navigator.clipboard` is undefined. The util carries the execCommand
// fallback that keeps this working there.
//
// The SUCCESS toast deliberately does NOT echo what was copied. It used to, and
// with a comparison set that meant a wall of text — the summary plus a URL
// carrying every msr id in full — covering the charts the engineer had just
// come back to read. A confirmation only has to confirm; the text is already on
// the clipboard, which is where it was wanted.
const copyToClipboard = async (text: string, okTitle: string) => {
  if (await copyTextToClipboard(text)) {
    toast.add({ title: okTitle, icon: 'i-lucide-clipboard-check', color: 'success' })
  } else {
    toast.add({ title: '복사하지 못했습니다', description: text, icon: 'i-lucide-triangle-alert', color: 'warning', ui: copyToastUi })
  }
}

const route = useRoute()
const { createShortLink } = useShortLink()

// A `/s/<code>` link when the shortener answers, the full URL when it does not.
// Never a failure: the user asked for a link, and the long one still works.
const linkToShare = async () => (await createShortLink(route.fullPath)) ?? props.ws.shareUrl()

const share = async () => copyToClipboard(await linkToShare(), '링크가 복사되었습니다')

// Selection facts as paste-ready text (messenger / report hand-off). The link
// rides along shortened for the same reason it does in `share` — in a set the
// URL was by far the longest line of the summary. The count is in the title
// because it is the one fact the (now bodyless) toast cannot otherwise convey:
// that the summary describes the FOCUS msr, out of several selected.
const copySummary = async () => {
  const sel = props.ws.selection.value
  if (!sel) return
  copyToClipboard(
    formatSelectionSummary(sel, props.analysis.activeParamLabel.value, await linkToShare()),
    isSet.value
      ? `요약이 복사되었습니다 · 세트 ${members.value.length}개 중 focus`
      : '요약이 복사되었습니다'
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
