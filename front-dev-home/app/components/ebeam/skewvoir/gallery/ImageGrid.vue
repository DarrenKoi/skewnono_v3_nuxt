<template>
  <div
    class="min-h-0 flex-1 overflow-auto"
    :style="{ '--cell': `${cell}px` }"
  >
    <!-- 목록: reading order, as many columns as the width allows. -->
    <div
      v-if="layout === 'list'"
      class="grid content-start gap-2"
      :style="{ gridTemplateColumns: 'repeat(auto-fill, minmax(var(--cell), 1fr))' }"
    >
      <template
        v-for="(item, i) in items"
        :key="i"
      >
        <slot
          name="cell"
          :chip="item.chip"
          :indexes="[i]"
        />
      </template>
    </div>

    <!-- 격자: one column per chip col, one row per chip row, bounded by the chips
         present. Empty dies are drawn faint so the spacing reads as a wafer, not
         as a bug. Sticky index headers keep the coordinates while scrolling. -->
    <div
      v-else
      class="grid w-max gap-1"
      :style="{ gridTemplateColumns: `auto repeat(${lattice.cols}, var(--cell))` }"
    >
      <div class="sticky top-0 left-0 z-20 bg-(--sk-surface)" />
      <div
        v-for="c in lattice.colLabels"
        :key="`c${c}`"
        class="sticky top-0 z-10 bg-(--sk-surface) pb-0.5 text-center font-mono text-xs text-(--sk-ink-subtle)"
      >
        {{ c }}
      </div>
      <template
        v-for="(r, ri) in lattice.rowLabels"
        :key="`r${r}`"
      >
        <div class="sticky left-0 z-10 flex items-center bg-(--sk-surface) pr-1.5 font-mono text-xs text-(--sk-ink-subtle)">
          {{ r }}
        </div>
        <template
          v-for="(c, ci) in lattice.colLabels"
          :key="`${c},${r}`"
        >
          <div
            v-if="occupied.get(`${ci + 1},${ri + 1}`)"
            class="flex flex-col gap-1"
          >
            <slot
              name="cell"
              :chip="occupied.get(`${ci + 1},${ri + 1}`)!.chip"
              :indexes="occupied.get(`${ci + 1},${ri + 1}`)!.indexes"
            />
          </div>
          <div
            v-else
            class="aspect-square rounded-(--sk-r-chip) border border-dashed border-(--sk-border-soft)"
          />
        </template>
      </template>
    </div>

    <!-- Items whose chip_number does not parse cannot be placed; listed rather
         than dropped or guessed onto (0,0). -->
    <div
      v-if="layout === 'lattice' && unplaced.length"
      class="mt-3 flex flex-col gap-1"
    >
      <span class="sk-meta">위치를 알 수 없는 항목</span>
      <div
        class="grid gap-2"
        :style="{ gridTemplateColumns: 'repeat(auto-fill, minmax(var(--cell), 1fr))' }"
      >
        <template
          v-for="i in unplaced"
          :key="i"
        >
          <slot
            name="cell"
            :chip="items[i]!.chip"
            :indexes="[i]"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { buildChipLattice } from '~/utils/skewvoirAnalysis/chipLattice'
import type { GalleryLayout } from '~/composables/useSkewvoirGalleryLayout'

const props = defineProps<{
  items: { chip: string }[]
  layout: GalleryLayout
  cell: number
  // Chips that define the lattice axes when they are a superset of `items` —
  // the full queue, so toggling a filter empties cells instead of reshaping
  // the table under the reader.
  axisChips?: string[]
}>()

defineSlots<{ cell: (p: { chip: string, indexes: number[] }) => unknown }>()

const lattice = computed(() => buildChipLattice([...(props.axisChips ?? []), ...props.items.map(i => i.chip)]))

// grid "col,row" → the chip there and every item index on it. A die measured
// at several MPs stacks its cards inside the one cell.
const occupied = computed(() => {
  const map = new Map<string, { chip: string, indexes: number[] }>()
  props.items.forEach((item, i) => {
    const pos = lattice.value.cells.get(item.chip)
    if (!pos) return
    const key = `${pos.col},${pos.row}`
    const hit = map.get(key)
    if (hit) hit.indexes.push(i)
    else map.set(key, { chip: item.chip, indexes: [i] })
  })
  return map
})

const unplaced = computed(() =>
  props.items.flatMap((item, i) => (lattice.value.cells.has(item.chip) ? [] : [i]))
)
</script>
