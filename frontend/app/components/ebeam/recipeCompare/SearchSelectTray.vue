<script setup lang="ts">
import type { RecipeSelectionCapabilities, RecipeSelectionEntry } from '~/utils/recipeSelection'
import { recipePairKey } from '~/utils/recipePair'

defineProps<{
  selected: RecipeSelectionEntry[]
  capabilities: RecipeSelectionCapabilities
}>()

const emit = defineEmits<{
  // Selection identity is the (name, fab) pair — see useRecipeSelectionSet —
  // so removing a chip must name both to disambiguate the same recipe name
  // selected from two different fabs.
  remove: [name: string, fabName: string]
  clear: []
  open: []
  lateral: []
  measHist: []
  compare: []
}>()
</script>

<template>
  <section class="dashboard-surface rounded-2xl border border-(--sk-brand)/35 p-4 shadow-sm xl:sticky xl:top-0">
    <div class="flex items-center justify-between gap-3">
      <div>
        <p class="flex items-center gap-1.5 sk-title">
          <UIcon
            name="i-lucide-shopping-basket"
            class="h-4 w-4 text-(--sk-brand)"
          />
          작업 세트
        </p>
        <p class="mt-0.5 sk-meta">
          선택한 Recipe {{ selected.length }}개
        </p>
      </div>
      <UButton
        v-if="selected.length"
        size="xs"
        color="neutral"
        variant="ghost"
        icon="i-lucide-trash-2"
        label="비우기"
        @click="emit('clear')"
      />
    </div>

    <div
      v-if="selected.length"
      class="mt-3 flex max-h-64 flex-wrap content-start gap-1.5 overflow-y-auto"
    >
      <span
        v-for="entry in selected"
        :key="recipePairKey(entry.fab_name, entry.name)"
        class="inline-flex max-w-full items-center gap-1 rounded-[var(--sk-r-chip)] bg-(--sk-brand-soft)/60 py-1.5 pl-2.5 pr-1 font-mono text-xs text-(--sk-ink)"
      >
        <span
          v-if="entry.fab_name"
          class="sk-fab-badge shrink-0"
        >{{ entry.fab_name }}</span>
        <span class="truncate">{{ entry.name }}</span>
        <button
          type="button"
          class="shrink-0 rounded-md p-0.5 text-(--sk-ink-muted) transition hover:bg-zinc-300 hover:text-(--sk-ink) dark:hover:bg-zinc-600"
          :aria-label="`Remove ${entry.name}`"
          @click="emit('remove', entry.name, entry.fab_name)"
        >
          <UIcon
            name="i-lucide-x"
            class="h-3 w-3"
          />
        </button>
      </span>
    </div>
    <div
      v-else
      class="mt-3 rounded-xl border border-dashed border-(--sk-border) px-4 py-8 text-center"
    >
      <UIcon
        name="i-lucide-list-checks"
        class="mx-auto h-5 w-5 text-(--sk-ink-muted)"
      />
      <p class="mt-2 sk-body">
        Recipe를 선택해주세요
      </p>
      <p class="mt-1 sk-meta">
        결과 표의 체크박스로 작업 세트를 구성할 수 있습니다.
      </p>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-2">
      <UButton
        v-if="!selected.length || capabilities.open"
        color="neutral"
        variant="outline"
        icon="i-lucide-file-search"
        label="열어보기"
        class="justify-center"
        :disabled="!selected.length"
        @click="emit('open')"
      />
      <UButton
        color="neutral"
        variant="outline"
        icon="i-lucide-network"
        label="횡전개"
        class="justify-center"
        :disabled="!selected.length"
        @click="emit('lateral')"
      />
      <UButton
        color="neutral"
        variant="outline"
        icon="i-lucide-history"
        label="측정이력"
        class="justify-center"
        :disabled="!selected.length"
        @click="emit('measHist')"
      />
      <UButton
        v-if="!selected.length || capabilities.compare"
        color="primary"
        variant="solid"
        icon="i-lucide-scale"
        label="비교하기"
        class="justify-center"
        :disabled="!selected.length"
        @click="emit('compare')"
      />
    </div>
  </section>
</template>
