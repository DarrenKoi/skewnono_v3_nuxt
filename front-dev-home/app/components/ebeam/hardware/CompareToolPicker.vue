<template>
  <div class="flex flex-wrap items-center gap-2 rounded-xl bg-(--sk-surface) px-3 py-2 ring-1 ring-(--sk-border-soft)">
    <span class="inline-flex items-center gap-1.5 sk-eyebrow">
      <UIcon
        name="i-lucide-git-compare"
        class="h-3.5 w-3.5"
      />
      비교 장비
    </span>

    <!-- ◆ = the selected (primary) tool, always shown as the comparison anchor. -->
    <span class="font-mono text-[11px] font-bold text-(--sk-ink)">◆ {{ selectedEqp || '—' }}</span>

    <USelectMenu
      v-model:open="menuOpen"
      v-model:search-term="searchTerm"
      :model-value="modelValue"
      multiple
      ignore-filter
      :reset-search-term-on-select="false"
      value-key="value"
      :items="items"
      :search-input="{ placeholder: '장비 ID 검색…' }"
      icon="i-lucide-plus"
      size="xs"
      class="min-w-[16rem] flex-1"
      :disabled="siblingIds.length === 0"
      :ui="{ itemTrailingIcon: 'hidden' }"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <!-- The stock trigger label resolves each picked value against `items`,
           which is now the FILTERED list — so with a search active any pick
           that doesn't match would silently drop out of the label, and if none
           matched the trigger would fall back to the placeholder and read as
           "nothing selected" while tools are in fact picked. Labelling straight
           from modelValue sidesteps that; label === value === eqp id, so the
           text is identical. `selectUi` is the component's own resolved class
           set, so this restyles nothing. -->
      <template #default="{ ui: selectUi }">
        <span
          v-if="modelValue.length > 0"
          :class="selectUi.value()"
        >{{ modelValue.join(', ') }}</span>
        <span
          v-else
          :class="selectUi.placeholder()"
        >비교할 장비 선택</span>
      </template>

      <!-- Leading checkbox sits right before the tool name (no far-right gap);
           the default trailing check is hidden via :ui above. -->
      <template #item-leading="{ item }">
        <span
          class="flex h-4 w-4 items-center justify-center rounded border"
          :class="modelValue.includes(item.value)
            ? 'border-(--sk-ink) bg-(--sk-ink) text-white dark:text-zinc-900'
            : 'border-(--sk-border)'"
        >
          <UIcon
            v-if="modelValue.includes(item.value)"
            name="i-lucide-check"
            class="h-3 w-3"
          />
        </span>
      </template>

      <!-- Bulk actions act on the matches, so they belong below the list they
           describe — #content-top renders above the search input. 닫기 is an
           explicit close affordance (click-outside / Esc also close the menu). -->
      <template #content-bottom>
        <div class="flex items-center gap-1 border-t border-(--sk-border-soft) p-1">
          <UButton
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-list-checks"
            :disabled="unpicked.length === 0"
            @click="selectMatches"
          >
            {{ isSearching ? `검색 결과 ${matches.length}대 선택` : `전체 선택 ${matches.length}` }}
          </UButton>
          <UButton
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-eraser"
            :disabled="pickedMatches.length === 0"
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

    <span class="font-mono text-[11px] text-(--sk-ink-muted) tabular-nums">
      동일 fab 장비 {{ siblingIds.length }}대 · 비교 {{ modelValue.length }}대
    </span>
  </div>
</template>

<script setup lang="ts">
// Shared multi-tool selector for the MDC/SCE comparison views. The picked set
// is owned by the parent (page-scoped state), so this component is a controlled
// input: it reads `modelValue` and emits changes, never mutating anything.
import { filterToolIds } from '~/utils/hardwareCompare'

const props = defineProps<{
  siblingIds: string[]
  selectedEqp: string
  modelValue: string[]
}>()

const emit = defineEmits<{ 'update:modelValue': [ids: string[]] }>()

// Controlled open state so the 닫기 button can close the menu; outside-click and
// Esc still close it because Reka emits update:open through this binding.
const menuOpen = ref(false)

// Filtering is ours (`ignore-filter`), not USelectMenu's. The bulk buttons have
// to act on exactly the rows on screen, and the only way those two sets cannot
// disagree is for one array to be both. `reset-search-term-on-select` is off for
// the same reason: the default wipes the search after every click, which would
// drop the filter halfway through picking a family of tools.
const searchTerm = ref('')
const isSearching = computed(() => searchTerm.value.trim().length > 0)

const matches = computed(() => filterToolIds(props.siblingIds, searchTerm.value))
const items = computed(() => matches.value.map(id => ({ label: id, value: id })))

// Both bulk actions are scoped to the matches: 전체 선택 unions them into the
// existing picks so tools chosen under an earlier search survive, and 해제
// subtracts only them. With an empty box the matches are every sibling, so 해제
// still reads as a plain "clear all".
const unpicked = computed(() => matches.value.filter(id => !props.modelValue.includes(id)))
const pickedMatches = computed(() => matches.value.filter(id => props.modelValue.includes(id)))

const selectMatches = () => emit('update:modelValue', [...props.modelValue, ...unpicked.value])
const clearMatches = () => emit('update:modelValue', props.modelValue.filter(id => !matches.value.includes(id)))
</script>
