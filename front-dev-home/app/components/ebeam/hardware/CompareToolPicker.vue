<template>
  <div class="flex flex-wrap items-center gap-2 rounded-xl bg-(--sk-surface) px-3 py-2 ring-1 ring-(--sk-border-soft)">
    <span class="inline-flex items-center gap-1.5 sk-label">
      <UIcon
        name="i-lucide-git-compare"
        class="h-3.5 w-3.5"
      />
      비교 장비
    </span>

    <!-- ◆ = the selected (primary) tool, always shown as the comparison anchor. -->
    <span class="font-mono text-xs font-bold text-(--sk-ink)">◆ {{ selectedEqp || '—' }}</span>

    <USelectMenu
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
      class="min-w-[16rem] flex-1"
      :disabled="siblingIds.length === 0"
      :ui="{ itemTrailingIcon: 'hidden' }"
      @update:model-value="emit('update:modelValue', $event)"
    >
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
            {{ isSearching ? `검색 결과 ${matches.length}대 선택` : `전체 ${matches.length}대 선택` }}
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

    <span class="font-mono text-xs text-(--sk-ink-muted) tabular-nums">
      동일 fab 장비 {{ siblingIds.length }}대 · 비교 {{ modelValue.length }}대
    </span>
  </div>
</template>

<script setup lang="ts">
// Shared multi-tool selector for the MDC/SCE comparison views. The picked set
// is owned by the parent (page-scoped state), so this component is a controlled
// input: it reads `modelValue` and emits changes, never mutating anything.
import { filterByTerm } from '~/utils/hardwareCompare'

const props = defineProps<{
  siblingIds: string[]
  selectedEqp: string
  modelValue: string[]
}>()

const emit = defineEmits<{ 'update:modelValue': [ids: string[]] }>()

// Controlled open state so the 닫기 button can close the menu; outside-click and
// Esc still close it because Reka emits update:open through this binding.
const menuOpen = ref(false)

// We filter, not USelectMenu (`ignore-filter`) — see filterByTerm for why.
// `reset-search-term-on-select` follows from the same requirement: the default
// wipes the search after every click, which would drop the filter halfway
// through picking a family of tools.
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

const selectMatches = () => emit('update:modelValue', [...props.modelValue, ...unpicked.value])
const clearMatches = () => emit('update:modelValue', props.modelValue.filter(id => !matches.value.includes(id)))
</script>
