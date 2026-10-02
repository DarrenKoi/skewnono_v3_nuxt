<template>
  <div
    v-if="rows.length"
    class="grid grid-cols-1 md:grid-cols-[minmax(0,13rem)_1fr] gap-4"
  >
    <nav
      :aria-label="navLabel"
      class="flex flex-row md:flex-col gap-1 overflow-x-auto md:overflow-visible border-b md:border-b-0 md:border-r border-(--sk-border) pb-2 md:pb-0 md:pr-3"
    >
      <button
        v-for="row in rows"
        :key="row.key"
        type="button"
        :aria-pressed="selectedKey === row.key"
        class="flex items-center justify-between gap-2 rounded-lg px-3 py-1.5 text-sm shrink-0 w-full text-left transition-colors"
        :class="selectedKey === row.key
          ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 font-semibold shadow-sm'
          : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'"
        @click="selectedKey = row.key"
      >
        <span class="truncate">
          <span
            v-if="row.prefix"
            class="text-xs font-normal opacity-70 mr-1"
          >{{ row.prefix }}</span>
          <span class="font-semibold tracking-wide">{{ row.label }}</span>
        </span>
        <span class="tabular-nums text-xs shrink-0 opacity-80">
          {{ countLabel }} {{ row.total.toLocaleString() }}명
        </span>
      </button>
    </nav>
    <ActivityFeatureBarList
      :items="selectedPages"
      :empty-text="emptyText"
    />
  </div>
  <div
    v-else
    class="sk-body"
  >
    {{ emptyText }}
  </div>
</template>

<script setup lang="ts">
import type { RailRow } from '~/utils/activityFamily'

// A rail of groups on the left, the selected group's top pages on the right.
// Shared by the Fab card and the tool-family card, which differ only in what
// a row is and what its count means.
const props = defineProps<{
  rows: RailRow[]
  /** The word in front of each count — 활성 (active users) or 조회 (people who
   *  opened a page). They are different numbers, so the card says which. */
  countLabel: string
  /** Accessible name of the rail, e.g. "Fab 선택". Not `ariaLabel`: Vue
   *  treats aria-* as a plain attribute, so the prop would never receive it. */
  navLabel: string
  emptyText: string
}>()

// Opens on the first group anyone actually used rather than on a row of
// zeros, and falls back to that again when the selection leaves the list
// (a window switch can drop a fab).
const selectedKey = ref<string | null>(null)
watchEffect(() => {
  if (selectedKey.value && props.rows.some(row => row.key === selectedKey.value)) return
  selectedKey.value = (props.rows.find(row => row.total > 0) ?? props.rows[0])?.key ?? null
})

const selectedPages = computed(() =>
  props.rows.find(row => row.key === selectedKey.value)?.pages ?? []
)
</script>
