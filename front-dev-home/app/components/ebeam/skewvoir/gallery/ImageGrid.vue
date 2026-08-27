<template>
  <div
    class="min-h-0 flex-1 overflow-auto"
    :style="{ '--cell': `${cell}px` }"
  >
    <!-- 목록: reading order, as many columns as the width allows. -->
    <div
      v-if="layout === 'list'"
      :class="FLOW"
    >
      <template
        v-for="(item, i) in items"
        :key="i"
      >
        <slot
          name="cell"
          :items="[item]"
        />
      </template>
    </div>

    <!-- 격자: one column per chip col, one row per chip row (compacted — see
         chipLattice.ts). Empty dies are drawn faint so the spacing reads as a
         wafer, not as a bug. Sticky index headers keep the coordinates while
         scrolling. -->
    <div
      v-else
      class="grid w-max gap-1"
      :style="{ gridTemplateColumns: `auto repeat(${lattice.colLabels.length}, var(--cell))` }"
    >
      <div class="sticky top-0 left-0 z-20 bg-(--sk-surface)" />
      <div
        v-for="c in lattice.colLabels"
        :key="c"
        class="sticky top-0 z-10 bg-(--sk-surface) pb-0.5 text-center font-mono text-xs text-(--sk-ink-subtle)"
      >
        {{ c }}
      </div>
      <template
        v-for="row in rows"
        :key="row.label"
      >
        <div class="sticky left-0 z-10 flex items-center bg-(--sk-surface) pr-1.5 font-mono text-xs text-(--sk-ink-subtle)">
          {{ row.label }}
        </div>
        <div
          v-for="(hit, ci) in row.cells"
          :key="ci"
          :class="hit ? 'flex flex-col gap-1' : 'aspect-square rounded-(--sk-r-chip) border border-dashed border-(--sk-border-soft)'"
        >
          <slot
            v-if="hit"
            name="cell"
            :items="hit"
          />
        </div>
      </template>
    </div>

    <!-- Items whose chip_number does not parse cannot be placed; listed rather
         than dropped or guessed onto (0,0). -->
    <div
      v-if="layout === 'lattice' && unplaced.length"
      class="mt-3 flex flex-col gap-1"
    >
      <span class="sk-meta">위치를 알 수 없는 항목</span>
      <div :class="FLOW">
        <template
          v-for="(item, i) in unplaced"
          :key="i"
        >
          <slot
            name="cell"
            :items="[item]"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T extends { chip: string }">
import type { ChipLattice } from '~/utils/skewvoirAnalysis/chipLattice'
import type { GalleryLayout } from '~/composables/useSkewvoirGalleryLayout'

const props = defineProps<{
  items: T[]
  // Built by the caller so its axes can come from a superset of `items` (the
  // unfiltered queue): toggling a filter then empties cells instead of
  // reshaping the table under the reader.
  lattice: ChipLattice
  layout: GalleryLayout
  cell: number
}>()

defineSlots<{ cell: (p: { items: T[] }) => unknown }>()

// Flow grid shared by 목록 and the unplaced list: as many --cell columns as fit.
const FLOW = 'grid content-start gap-2 [grid-template-columns:repeat(auto-fill,minmax(var(--cell),1fr))]'

// Lattice rows as a dense table: `cells[ci]` is the items on that die, or null
// for an empty die. A die measured at several MPs stacks its cards in one cell.
const rows = computed(() => {
  const { colLabels, rowLabels, cells } = props.lattice
  const grid = rowLabels.map(label => ({ label, cells: colLabels.map((): T[] | null => null) }))
  for (const item of props.items) {
    const pos = cells.get(item.chip)
    if (!pos) continue
    const row = grid[pos.row - 1]!.cells
    ;(row[pos.col - 1] ??= []).push(item)
  }
  return grid
})

const unplaced = computed(() => props.items.filter(item => !props.lattice.cells.has(item.chip)))
</script>
