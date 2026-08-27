<template>
  <div class="flex flex-col gap-2.5 rounded-xl bg-(--sk-surface) px-3 py-2 ring-1 ring-(--sk-border-soft)">
    <!-- ===== bar: identity + picked tokens + count (identical in both modes) ===== -->
    <div class="flex flex-wrap items-center gap-2">
      <span class="inline-flex items-center gap-1.5 sk-label">
        <UIcon
          name="i-lucide-git-compare"
          class="h-3.5 w-3.5"
        />
        비교 장비
      </span>

      <!-- ◆ = the selected (primary) tool, always shown as the comparison
           anchor. Terracotta, not ink: it is the subject the picked tools are
           read against, and the ink fill is spoken for by the chips below. -->
      <span class="font-mono text-xs font-bold text-(--sk-brand)">◆ {{ selectedEqp || '—' }}</span>

      <span
        v-if="modelValue.length"
        class="h-4 w-px bg-(--sk-border-soft)"
      />

      <!-- Picked tools as removable tokens. In grid mode this repeats the
           filled chips below, and that repetition is the point: the grid caps
           its height and scrolls, so the bar is the one place the whole picked
           set stays legible. -->
      <span
        v-for="id in modelValue"
        :key="id"
        class="inline-flex items-center gap-1.5 rounded-[var(--sk-r-chip)] border border-(--sk-border) bg-(--sk-muted-surface) py-0.5 pr-1.5 pl-2 font-mono text-xs text-(--sk-ink)"
      >
        <span
          class="h-1.5 w-1.5 rounded-full"
          :style="{ background: compareColors[id] }"
        />
        {{ id }}
        <button
          type="button"
          class="text-(--sk-ink-subtle) transition-colors hover:text-(--sk-bad)"
          :aria-label="`${id} 비교에서 제거`"
          @click="toggle(id)"
        >
          <UIcon
            name="i-lucide-x"
            class="block h-3 w-3"
          />
        </button>
      </span>

      <!-- 40대+ only — under 40 the grid stands open and there is nothing to
           trigger. -->
      <USelectMenu
        v-if="!gridMode"
        v-model:open="menuOpen"
        v-model:search-term="searchTerm"
        :model-value="modelValue"
        multiple
        ignore-filter
        :reset-search-term-on-select="false"
        :items="matches"
        :search-input="{ placeholder: '장비 ID 검색…' }"
        placeholder="비교할 장비 선택"
        icon="i-lucide-plus"
        size="xs"
        class="w-44"
        :ui="{ content: MENU_CONTENT, group: MENU_GROUP, itemTrailingIcon: 'hidden' }"
        @update:model-value="emit('update:modelValue', $event)"
      >
        <!-- The multi-select default would print every picked id into a 11rem
             trigger; the tokens beside it already carry that list. Overriding
             the slot drops the theme's own `data-slot="placeholder"` styling,
             so the empty state has to restate the muted colour by hand —
             without it an empty picker reads as a filled value (DESIGN.md:
             "values are ink, labels are muted"). -->
        <template #default>
          <span :class="modelValue.length ? 'truncate' : 'truncate text-(--sk-ink-subtle)'">
            {{ modelValue.length ? '장비 추가 · 변경' : '비교할 장비 선택' }}
          </span>
        </template>

        <!-- Leading checkbox sits right before the tool name (no far-right gap);
             the default trailing check is hidden via :ui above. -->
        <template #item-leading="{ item }">
          <AppSelectCheck :checked="modelValue.includes(item)" />
        </template>

        <!-- Bulk actions act on the matches, so they belong below the list they
             describe — #content-top renders above the search input. 닫기 is an
             explicit close affordance (click-outside / Esc also close the menu).

             The footer sits INSIDE the listbox, so Enter/Space on a focused
             button bubbles to Reka, which cancels the native activation and
             toggles the highlighted option instead — Tab here and press Enter
             and you would pick one tool rather than all matches. Stopping the
             key at the footer lets the buttons behave like buttons. -->
        <template #content-bottom>
          <div
            class="flex items-center gap-1 border-t border-(--sk-border-soft) p-1"
            @keydown.enter.stop
            @keydown.space.stop
          >
            <UButton
              size="xs"
              color="neutral"
              variant="soft"
              icon="i-lucide-list-checks"
              :disabled="unpicked.length === 0"
              @click="selectMatches"
            >
              {{ selectAllLabel }}
            </UButton>
            <UButton
              size="xs"
              color="neutral"
              variant="soft"
              icon="i-lucide-eraser"
              :disabled="!hasPickedMatch"
              @click="clearMatches"
            >
              해제
            </UButton>
            <UButton
              class="ml-auto"
              size="xs"
              color="neutral"
              variant="soft"
              icon="i-lucide-check"
              @click="menuOpen = false"
            >
              닫기
            </UButton>
          </div>
        </template>
      </USelectMenu>

      <span class="ml-auto font-mono text-xs whitespace-nowrap text-(--sk-ink-muted) tabular-nums">
        동일 fab 장비 {{ siblingIds.length }}대 · 비교 {{ modelValue.length }}대
      </span>
    </div>

    <!-- ===== under 40대: the grid stands open — click a chip to toggle ===== -->
    <div
      v-if="gridMode"
      class="flex flex-col gap-2 border-t border-(--sk-border-soft) pt-2.5"
    >
      <p
        v-if="siblingIds.length === 0"
        class="sk-meta"
      >
        같은 fab에 비교할 장비가 없습니다.
      </p>
      <template v-else>
        <!-- Same cap as the 장비 선택 strip above: a picker taller than about
             four rows pushes the table it exists to configure below the fold. -->
        <div
          role="group"
          aria-label="비교 장비 선택"
          class="flex max-h-[9.5rem] flex-wrap gap-1.5 overflow-y-auto"
        >
          <SkChip
            v-for="id in siblingIds"
            :key="id"
            size="sm"
            tone="ink"
            :active="modelValue.includes(id)"
            @click="toggle(id)"
          >
            <span class="inline-flex items-center gap-1.5 font-mono">
              <!-- The dot is the tool's comparison colour — the same one its
                   table column, boxplot marker and trend curve take. Absent
                   while unpicked, because it has no colour until then. -->
              <span
                v-if="modelValue.includes(id)"
                class="h-1.5 w-1.5 rounded-full"
                :style="{ background: compareColors[id] }"
              />
              {{ id }}
            </span>
          </SkChip>
        </div>

        <div class="flex items-center gap-1">
          <UButton
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-list-checks"
            :disabled="unpicked.length === 0"
            @click="selectMatches"
          >
            {{ selectAllLabel }}
          </UButton>
          <UButton
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-eraser"
            :disabled="!hasPickedMatch"
            @click="clearMatches"
          >
            해제
          </UButton>
          <span class="ml-auto sk-meta">칩을 클릭해 켜고 끕니다 · 선택 색 = 차트·테이블 색</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
// Shared multi-tool selector for the MDC/SCE comparison views. The picked set
// is owned by the parent (page-scoped state), so this component is a controlled
// input: it reads `modelValue` and emits changes, never mutating anything.
//
// ONE component, TWO modes, chosen by the cohort size rather than by a prop
// (design 2a, 2026-08-28). The fab cohort is whatever the service payload
// returns — the home mock builds 3–5 siblings, the office adapters hand back
// the whole fab map (30–60 tools) — so neither shape can be the only one the
// picker handles:
//
//   < 40대  inline chip grid, always open. No search: every tool is on screen
//           and one click toggles it, which is the grammar the 장비 선택 strip
//           above already taught. The only mode home development ever sees.
//   ≥ 40대  the grid would run 4–6 rows and push the table under the fold, so
//           it folds into the (widened, 3-column) menu and the bar keeps a
//           trigger. Search earns its place only here.
//
// The bar — ◆ anchor, removable tokens, the count — is identical across both,
// so moving to a bigger fab never changes what the control looks like it does.
import { filterByTerm } from '~/utils/hardwareCompare'

const props = defineProps<{
  siblingIds: string[]
  selectedEqp: string
  modelValue: string[]
  // The parent's OWN assignCompareColors map, not a second call to it here:
  // the assignment is index-based, so an independent copy would drift the day a
  // panel scopes its ids differently, and a token whose dot disagrees with its
  // table column is worse than no dot at all.
  compareColors: Record<string, string>
}>()

const emit = defineEmits<{ 'update:modelValue': [ids: string[]] }>()

// About four rows of eqp_id chips inside the 9.5rem cap — past that the grid
// starts scrolling more than it shows. Nothing downstream reads it.
const POPOVER_AT = 40
const gridMode = computed(() => props.siblingIds.length < POPOVER_AT)

// The menu widens past its trigger — NuxtUI pins a popper to the trigger width
// (same rule as pmPlanning/ToolPicker) — and lays its items out in three
// columns, which is what keeps 40+ tools on one screen instead of behind a long
// scroll. Arrow keys then walk the grid in reading order (right, then wrap)
// rather than straight down; every item stays reachable.
//
// The width is stated, not `w-auto min-w-full`: a 1fr grid takes its columns
// from the box rather than growing it, so `auto` collapses the panel back to
// the trigger's own width and the three columns come out ~55px each.
// The height cap lives on `content`, not `viewport`: the theme's own 15rem is
// on the panel, so raising only the scroll area changes nothing. Three columns
// only pay off if the panel is tall enough to show them.
const MENU_CONTENT = [
  'w-[min(32rem,calc(100vw-2rem))]',
  'max-h-[min(24rem,var(--reka-combobox-content-available-height,24rem))]'
].join(' ')
const MENU_GROUP = 'grid grid-cols-3 gap-x-1'

// Controlled open state so the 닫기 button can close the menu; outside-click and
// Esc still close it because Reka emits update:open through this binding.
const menuOpen = ref(false)

// We filter, not USelectMenu (`ignore-filter`) — see filterByTerm for why.
// `reset-search-term-on-select` follows from the same requirement: the default
// wipes the search after every click, which would drop the filter halfway
// through picking a family of tools. Grid mode never writes searchTerm, so
// `matches` is every sibling there and the bulk actions need no mode branch.
const searchTerm = ref('')
const isSearching = computed(() => searchTerm.value.trim().length > 0)

// Items are plain ids: USelectMenu renders a string item as its own label and
// value, so there is nothing for a {label, value} wrapper to add here.
const matches = computed(() => filterByTerm(props.siblingIds, searchTerm.value, id => id))

// Both bulk actions are scoped to the matches: 전체 선택 unions them into the
// existing picks so tools chosen under an earlier search survive, and 해제
// subtracts only them. With an empty box the matches are every sibling, so 해제
// still reads as a plain "clear all".
const unpicked = computed(() => matches.value.filter(id => !props.modelValue.includes(id)))
const hasPickedMatch = computed(() => matches.value.some(id => props.modelValue.includes(id)))
const selectAllLabel = computed(() =>
  isSearching.value ? `검색 결과 ${matches.value.length}대 선택` : `전체 ${matches.value.length}대 선택`)

const selectMatches = () => emit('update:modelValue', [...props.modelValue, ...unpicked.value])
const clearMatches = () => emit('update:modelValue', props.modelValue.filter(id => !matches.value.includes(id)))

const toggle = (id: string) => emit(
  'update:modelValue',
  props.modelValue.includes(id) ? props.modelValue.filter(picked => picked !== id) : [...props.modelValue, id]
)
</script>
