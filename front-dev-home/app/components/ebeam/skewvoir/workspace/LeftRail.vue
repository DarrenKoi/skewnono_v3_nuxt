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
                class="block truncate text-xs"
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

         Which views let you click a member is `canSwitchFocus` below, and the
         reasoning is at `rendersFocusAlone` (utils/skewvoirAnalysis/curatedSet.ts).

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
          class="inline-flex items-center gap-1 rounded-(--sk-r-chip) px-1.5 py-0.5 text-xs font-semibold"
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

      <!-- Compact counts. 호환 goes to an em dash — and drops the OK colour for
           the neutral chip — when nothing was counted, because the manifest
           derives the count from the files that loaded and the focus loads on
           its own path: with no set files it compares the focus against itself
           and reports 호환 1 beside a nine-row member list.
           isSetCompatibilityKnown owns that line and names the two situations
           it covers (a cold set load, and the Dashboard permanently).

           제외 needs no such gate: it is already hidden at 0, and 0 is exactly
           what an uncounted set yields, so it stays silent rather than
           claiming nothing was excluded. -->
      <div class="flex flex-wrap items-center gap-1 px-1">
        <span
          class="rounded-(--sk-r-chip) px-1.5 py-0.5 font-mono text-xs"
          :class="compatibilityKnown
            ? 'bg-(--sk-ok-soft) text-(--sk-ok)'
            : 'bg-(--sk-chip-bg) text-(--sk-ink-muted)'"
          :title="compatibilityKnown ? undefined : '세트 파일을 불러온 뒤 계산됩니다.'"
        >호환 {{ compatibilityKnown ? counts.compatible : '—' }}</span>
        <span
          v-if="counts.excluded > 0"
          class="rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-1.5 py-0.5 font-mono text-xs text-(--sk-bad)"
        >제외 {{ counts.excluded }}</span>
      </div>

      <!-- Member list. One markup shape, two behaviours: `rowTag` swaps the row
           between a focus button and a plain div, so the two variants cannot
           drift apart in type, spacing or truncation. What differs is the
           interaction and the focus highlight that comes with it — an inert
           list marks nothing, because a set assembled to be read TOGETHER
           should not nominate one of its members. -->
      <div class="flex items-center justify-between gap-2 px-1">
        <span class="sk-meta">{{ isSet ? `비교 세트 · ${members.length}` : '측정' }}</span>
        <button
          v-if="canSwitchFocus"
          type="button"
          class="text-xs text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
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
            :is="rowTag"
            v-bind="rowAttrs(member)"
            class="flex w-full min-w-0 flex-col gap-0.5 rounded-(--sk-r-nav) px-2 py-1.5 text-left transition-colors"
            :class="rowClass(member)"
            :title="member.msr"
          >
            <!-- Both lines are DATA (a lot id, an equipment id, a capture
                 time), so both sit at the 12px floor DESIGN.md sets for a
                 value; the 11px tier is for chrome that names things. Weight
                 and colour carry the hierarchy between them instead. -->
            <span class="flex min-w-0 items-center gap-1.5">
              <span
                class="min-w-0 truncate font-mono text-[12px] font-semibold"
                :class="member.pressed ? '' : 'text-(--sk-ink)'"
              >{{ member.lot }}</span>
              <!-- DESIGN.md `category-tag`: a tag naming which peer group a row
                   belongs to, no verdict attached. Shaped after its named
                   reference, `ebeam/rules/MemoryChip.vue` — 6px radius, the
                   sanctioned neutral triple. NEUTRAL for every fab, never a
                   hue per value: with 17 fabs this is the ">= 3 values get no
                   colour encoding" case, so the four characters do the telling
                   apart and the tag is only a container. -->
              <span
                v-if="member.fab"
                class="shrink-0 rounded-[var(--sk-r-sidebar)] border px-1.5 font-mono text-xs"
                :class="member.pressed
                  ? 'border-transparent bg-(--sk-brand-fg)/20 text-(--sk-brand-fg)'
                  : 'border-(--sk-border) bg-(--sk-muted-surface) text-(--sk-ink-muted)'"
              >{{ member.fab }}</span>
            </span>
            <span
              v-if="member.sub"
              class="min-w-0 truncate font-mono text-[12px]"
              :class="member.pressed ? 'opacity-80' : 'text-(--sk-ink-muted)'"
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
          :disabled="action.disabled"
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
import { formatRecipeTimestamp, recipeDetailId, recipeDetailRoute } from '~/utils/recipeView'
import { isSetCompatibilityKnown, rendersFocusAlone } from '~/utils/skewvoirAnalysis/curatedSet'
import { formatSelectionSummary } from '~/utils/skewvoirAnalysis/summary'

const props = defineProps<{ ws: SkewvoirWorkspace, analysis: SkewvoirAnalysis }>()

const emit = defineEmits<{ openReadiness: [] }>()

const detailOpen = ref(false)

// A comparison set (scope=set with 2+ members) vs. a single measurement. It
// picks the section headings and the scope chip; the member ROWS render the
// same either way, because parseMsrList falls the `msrs` list back to the lone
// focus `msr`, so a single measurement is just a set of one.
const isSet = computed(() => props.analysis.scope.value === 'set' && props.analysis.msrList.value.length >= 2)

// Whether a member row may be clicked to move the focus. Two conditions, and
// both are about there being a choice to make: a view that draws ONE
// measurement and so needs to be told which (rendersFocusAlone owns that list
// and the reasoning behind it), and a SET — with one measurement there is
// nothing to switch to, and a lone row rendered as a permanently-pressed
// toggle offers a choice that isn't.
const canSwitchFocus = computed(() =>
  rendersFocusAlone(props.ws.activeKind.value) && isSet.value
)

const counts = computed(() => props.analysis.manifest.value.counts)

// Whether `counts.compatible` may be shown as a number. Reads setFiles rather
// than a pending flag on purpose — see isSetCompatibilityKnown.
const compatibilityKnown = computed(() => isSetCompatibilityKnown({
  members: props.analysis.msrList.value.length,
  loaded: props.analysis.setFiles.value.size
}))

interface RailMember {
  msr: string
  lot: string
  sub: string
  /** Empty unless the set actually spans fabs — see `namesFab` in `members`. */
  fab: string
  /** Drawn as the active row. Folded in here rather than left as a bare
   *  `active` flag because every consumer wants it AND-ed with canSwitchFocus:
   *  an inert list highlights nothing, so there is no second reading. */
  pressed: boolean
}

// One shape for every measurement in the rail: `lot` over `eqp · time`.
//
// The meas_hist row is the source. A DEEP-LINKED msr may have no row (the
// analysis route loads a file by msr alone, deliberately, so a shared link
// works before/without its history) — for the focus we then fall back to the
// identity the URL itself carries, which is exactly what those `lot`/`eq`/`cap`
// params exist for. With neither, the raw msr id stands in: unreadable at 240px
// but honest, and the `title` carries it in full for a hover.
//
// The URL fallback is built ONCE above the loop: it can only ever apply to the
// focus row, so deriving it per member was 30 evaluations of a string that has
// at most one consumer. It goes through formatRecipeTimestamp for the same
// reason msrLabel does — `cap` is a raw ISO stamp copied out of the meas_hist
// row, so without it a deep-linked row reads `ECDX285 · 2026-05-09T12:00:00Z`
// directly beneath siblings reading `ECDX285 · 2026-05-09 12:00`.
const members = computed<RailMember[]>(() => {
  const rows = props.analysis.rowByMsr.value
  const sel = props.ws.selection.value
  const focus = props.analysis.focusMsr.value
  const clickable = canSwitchFocus.value
  const msrs = props.analysis.msrList.value
  const cap = sel?.capturedAt && sel.capturedAt !== '—' ? formatRecipeTimestamp(sel.capturedAt) : ''
  const urlSub = [sel?.eq, cap].filter(Boolean).join(' · ')

  // A set CAN span fabs — the search is fab-filterable but does not have to be,
  // and comparing one recipe across fabs is a real reading. That matters here
  // because the recipe is a different copy in each fab, so a cross-fab set is
  // comparing measurements taken under settings that may genuinely differ.
  // Named only when it actually varies: at 240px the prefix costs the sub-line
  // its minutes, and a single-fab set has nothing to disambiguate.
  const fabs = new Set(msrs.map(msr => rows.get(msr)?.fab_name).filter(Boolean))
  const namesFab = fabs.size > 1

  return msrs.map((msr) => {
    const row = rows.get(msr)
    const isUrlFocus = sel?.msr === msr
    return {
      msr,
      lot: row?.lot_id || (isUrlFocus ? sel.lot : '') || msr,
      // msrLabel already reads `eqp · time` off the row; it returns the bare
      // msr id when there is no row, which would restate the line above it.
      sub: row ? props.analysis.msrLabel(msr) : (isUrlFocus ? urlSub : ''),
      // Beside the lot, NOT prepended to `sub`: at 240px `eqp · time` already
      // fills that line, and a fab prefix there truncates away the very
      // timestamp a Time-Series comparison is read by. The lot line has room.
      fab: namesFab && row ? row.fab_name : '',
      pressed: clickable && msr === focus
    }
  })
})

// The row's tag and its behavioural attributes, assembled together rather than
// re-branching on canSwitchFocus at each binding site. Mirrors sk/NavPill.vue's
// `resolvedTag` + `rootAttrs`, and for the same reason: nothing structurally
// stops a `:is` from drifting out of step with a separately-guarded `:type` or
// `@click`, so adding one attribute later means finding every guard. Here it is
// one object.
const rowTag = computed(() => (canSwitchFocus.value ? 'button' : 'div'))

const rowAttrs = (member: RailMember): Record<string, unknown> =>
  canSwitchFocus.value
    ? {
        'type': 'button',
        'aria-pressed': member.pressed,
        'onClick': () => props.analysis.setFocusedMsr(member.msr)
      }
    : {}

// State-only classes; the row's geometry stays at the call site.
const rowClass = (member: RailMember): string => {
  if (member.pressed) return 'bg-(--sk-brand) text-(--sk-brand-fg)'
  return canSwitchFocus.value ? 'hover:bg-(--sk-chip-bg)' : ''
}

// 선택 해제 — empty the set down to the focused MSR. Offered only where the
// focus is meaningful (a set on a focus-only view); the ⤢ modal's 세트 편집 is
// the general editor, and can add as well as remove.
const deselectToFocus = () => {
  const focus = props.analysis.focusMsr.value
  if (focus) props.ws.setMsrs([focus])
}

const toast = useToast()
const router = useRouter()

// The "Recipe 열어 보기" target for the focus measurement, in the existing
// recipe-detail page — or null when the measurement cannot address it yet.
//
// Every field comes off the meas_hist focus ROW, never off `selection`. The
// selection's `recipe` is the BARE display half (`ADI_CD_BIAS_001`) — the
// landing page actively strips the class prefix off recent entries — while the
// detail screens are addressed by the class-qualified `full_name`. Handing over
// the bare half is a 502 at the office AND at home, surfacing as
// "Recipe 내용을 불러오지 못했습니다." on the page that just opened.
// `recipeDetailId` (utils/recipeView.ts) owns that rule and its reasoning.
//
// The route is fab-scoped and the analysis route is not, so the fab comes off
// the same row. No row — meas_hist still loading, or a deep-linked msr it has
// no row for — DISABLES the button rather than dropping the click silently.
//
// The fab is not decoration: the same recipe name is a DIFFERENT recipe per
// fab (each fab's tools hold their own .idp, and the office adapter locates it
// per fab), so the button names the copy it is about to open rather than
// letting the reader assume there is only one.
const focusFab = computed(() => props.analysis.focusRow.value?.fab_name ?? '')

const recipeTarget = computed(() => {
  const row = props.analysis.focusRow.value
  if (!row || !focusFab.value) return null
  return recipeDetailRoute(props.ws.toolType, focusFab.value, 'open', recipeDetailId(row), 'redis', focusFab.value)
})

const openRecipe = () => {
  if (!recipeTarget.value) return
  window.open(router.resolve(recipeTarget.value).href, '_blank', 'noopener')
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
const actions = computed(() => [
  { label: '요약 복사', icon: 'i-lucide-clipboard-list', disabled: false, onClick: copySummary },
  {
    label: focusFab.value ? `Recipe 열어보기 · ${focusFab.value}` : 'Recipe 열어보기',
    icon: 'i-lucide-file-search',
    disabled: !recipeTarget.value,
    onClick: openRecipe
  },
  { label: 'Share', icon: 'i-lucide-share-2', disabled: false, onClick: share }
])
</script>
