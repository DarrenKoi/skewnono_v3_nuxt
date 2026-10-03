<template>
  <section class="dashboard-surface overflow-hidden rounded-(--sk-r-card)">
    <div class="flex items-center gap-3.5 px-4 py-3.5">
      <div class="min-w-0">
        <p class="sk-eyebrow">
          선택 포인트 · {{ index + 1 }} / {{ points.length }}
        </p>
        <p class="truncate font-mono text-xl font-bold tracking-tight text-(--sk-ink)">
          {{ selectedPoint || '–' }}
        </p>
      </div>
      <div class="ml-auto flex shrink-0 gap-1.5">
        <UButton
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-chevron-left"
          label="이전"
          :disabled="points.length < 2"
          @click="step(-1)"
        />
        <UButton
          size="sm"
          color="neutral"
          variant="outline"
          trailing-icon="i-lucide-chevron-right"
          label="다음"
          :disabled="points.length < 2"
          @click="step(1)"
        />
      </div>
    </div>

    <div class="grid grid-cols-1 border-t border-(--sk-border) xl:grid-cols-12">
      <div class="flex min-w-0 flex-col border-(--sk-border) max-xl:border-b xl:col-span-5 xl:border-r">
        <p
          v-if="!cards.length"
          class="flex flex-1 items-center justify-center px-4 py-10 sk-body"
        >
          이 포인트의 측정값이 없습니다.
        </p>
        <!-- One card per measurement column. A recipe can carry 51 of them, so
             the grid wraps and scrolls rather than fixing three across. Beside
             the chart (xl) it takes no height of its own (basis-0) and fills what
             the chart sets, so neither side leaves a gap. -->
        <div
          v-else
          class="grid max-h-72 flex-1 grid-cols-[repeat(auto-fit,minmax(11rem,1fr))] overflow-y-auto xl:basis-0 xl:max-h-none"
        >
          <div
            v-for="card in cards"
            :key="card.column"
            class="flex flex-col justify-between gap-3.5 border-b border-r border-(--sk-border-soft) p-4"
          >
            <p class="flex justify-between gap-1.5 sk-field-label">
              <span class="truncate">{{ card.column }}</span>
              <span class="shrink-0 sk-label">Δ vs MEAN</span>
            </p>
            <div
              v-for="(cell, i) in card.cells"
              :key="i"
            >
              <p class="truncate font-mono sk-label">
                {{ cell.block }}
              </p>
              <p class="flex items-baseline gap-2">
                <span
                  class="font-mono font-semibold tabular-nums text-(--sk-ink)"
                  :class="i === 0 ? 'text-2xl' : 'text-base'"
                >{{ cell.value }}</span>
                <span
                  v-if="cell.delta"
                  class="sk-value-num"
                >Δ {{ cell.delta }}</span>
              </p>
            </div>
          </div>
        </div>

        <div
          v-if="blocks.length"
          class="grid grid-cols-[repeat(auto-fit,minmax(14rem,1fr))] border-t border-(--sk-border-soft) bg-(--sk-muted-surface)"
        >
          <p
            v-for="(block, i) in blocks"
            :key="i"
            class="flex items-center gap-2 px-4 py-2.5"
          >
            <span class="truncate font-mono sk-meta">{{ block.name }}</span>
            <UBadge
              :label="block.row.State"
              :color="STATE_BADGE[block.row.State] ?? 'neutral'"
              variant="subtle"
            />
            <!-- Only a stated false is a failure; a missing cell is unknown. -->
            <span
              class="ml-auto shrink-0 sk-value-num font-semibold"
              :class="block.row.Valid === false ? 'text-(--sk-bad)' : ''"
            >Valid {{ formatPointCell(block.row.Valid) }}</span>
          </p>
        </div>
      </div>

      <AfmDetailSummaryScatterChart
        class="min-w-0 p-4 xl:col-span-7"
        :summary="summary"
        :point="selectedPoint"
        :blocks="blocks"
        :export-name="exportName"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  data: AfmDetailRow[]
  summary: AfmSummaryRow[]
  points: string[]
  exportName?: string
}>()

const selectedPoint = defineModel<string>('selectedPoint', { required: true })

const index = computed(() => props.points.indexOf(selectedPoint.value))
const step = (by: number) => {
  const count = props.points.length
  selectedPoint.value = props.points[(index.value + by + count) % count] ?? ''
}

const blocks = computed(() => blocksOfPoint(props.data, props.summary, selectedPoint.value))

// Every measurement column any of the point's blocks carries: a block the
// measurement stopped in has none, and shows a dash under the others.
const cards = computed(() =>
  derivePointColumns(blocks.value.map(block => block.row))
    .filter(column => isMeasurementKey(column.key))
    .map(column => ({
      column: column.key,
      cells: blocks.value.map((block) => {
        const value = summaryNumber(block.row[column.key])
        const mean = summaryNumber(
          props.summary.find(row => row.Site === block.name && row.ITEM === 'MEAN')?.[column.key]
        )
        return {
          block: block.name,
          value: value?.toFixed(2) ?? '–',
          delta: value !== null && mean !== null ? formatSignedNm(value - mean, 2) : ''
        }
      })
    }))
)
</script>
