<template>
  <div class="dashboard-surface flex flex-col gap-3 rounded-2xl p-4 lg:flex-row lg:items-center">
    <div class="min-w-0 flex-1">
      <div class="mb-1.5 flex items-center gap-2">
        <AppBackButton
          :to="backRoute"
          label="Recipe 검색"
          class="-ml-2"
        />
        <p class="sk-eyebrow text-(--sk-brand)">
          비교 대상 recipe · {{ entries.length }}
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <span
          v-for="entry in entries"
          :key="recipePairKey(entry.fab_name, entry.name)"
          class="inline-flex max-w-[240px] items-center gap-1 rounded-[var(--sk-r-chip)] bg-(--sk-brand-soft)/60 py-1 pl-2.5 pr-1 font-mono text-[11px] text-(--sk-ink)"
        >
          <span class="truncate">{{ entry.name }}</span>
          <button
            type="button"
            :aria-label="`Remove ${entry.name}`"
            class="rounded-md p-0.5 hover:bg-zinc-300 dark:hover:bg-zinc-600"
            @click="emit('remove', entry.name, entry.fab_name)"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
          </button>
        </span>
      </div>
    </div>

    <UButton
      class="shrink-0"
      size="sm"
      color="neutral"
      variant="solid"
      icon="i-lucide-download"
      label="Excel 다운로드"
      :disabled="!canExport"
      @click="emit('download')"
    />
  </div>
</template>

<script setup lang="ts">
import type { RecipeSelectionEntry } from '~/utils/recipeSelection'
import { recipePairKey } from '~/utils/recipePair'

defineProps<{
  entries: RecipeSelectionEntry[]
  backRoute: string
  canExport: boolean
}>()

const emit = defineEmits<{
  remove: [name: string, fabName: string]
  download: []
}>()
</script>
