<template>
  <AfmCard
    icon="i-lucide-target"
    title="측정 포인트"
    :count="availablePoints.length"
    flush
  >
    <template
      v-if="dots.length"
      #actions
    >
      <span class="sk-meta">Site {{ dots.length }}{{ perSite > 1 ? ` × ${perSite}` : '' }}</span>
    </template>

    <!-- Site index layout: only a recipe that records Site ID has Site X / Site Y
         to draw. Not a wafer outline — the two lines are index 0 on each axis
         (`siteDots` keeps index 0 at 50%), not a wafer centre. -->
    <div
      v-if="dots.length"
      class="px-4 pt-3"
    >
      <div class="relative h-[200px] overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border-soft) bg-(--sk-muted-surface)">
        <span
          aria-hidden="true"
          class="absolute inset-y-2 left-1/2 w-px bg-(--sk-border)"
        />
        <span
          aria-hidden="true"
          class="absolute inset-x-2 top-1/2 h-px bg-(--sk-border)"
        />
        <span class="absolute right-2 top-1.5 sk-eyebrow">Site X · Y</span>
        <button
          v-for="(dot, i) in dots"
          :key="dot.siteId"
          type="button"
          class="absolute min-w-[22px] -translate-x-1/2 -translate-y-1/2 rounded-(--sk-r-sidebar) border px-1 py-0.5 font-mono text-xs font-semibold tabular-nums transition-colors duration-200"
          :class="dot.siteId === selectedSite
            ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
            : 'border-(--sk-border) bg-(--sk-surface) text-(--sk-ink) hover:bg-(--sk-chip-bg)'"
          :style="{ left: `${dot.left}%`, top: `${dot.top}%` }"
          :title="dot.siteId"
          :aria-label="`Site ${dot.siteId}`"
          :aria-pressed="dot.siteId === selectedSite"
          @click="selectedPoint = dot.point"
        >
          {{ i + 1 }}
        </button>
      </div>
      <p class="mt-1.5 sk-hint">
        Site X · Site Y 인덱스의 배치이며 웨이퍼 형상이 아닙니다. 인덱스는 단위가 없고 Site Y 가 큰 쪽이 위이며, 두 선은 인덱스 0 입니다.
      </p>
    </div>

    <p
      v-if="firstColumn"
      class="flex justify-between px-4 pb-1 pt-3 sk-label"
    >
      <span>Point</span>
      <span>{{ firstColumn }}</span>
    </p>
    <!-- The card is sticky, so it has to fit a short window: everything but
         this list is about 28rem tall, and the list takes what is left. -->
    <ul class="max-h-[clamp(6rem,calc(100dvh-28rem),16rem)] space-y-0.5 overflow-y-auto px-2 pb-2 pt-1">
      <li
        v-for="point in points"
        :key="point.key"
      >
        <button
          type="button"
          class="grid w-full grid-cols-[8px_minmax(0,1fr)_auto] items-center gap-2 rounded-(--sk-r-chip) px-2 py-1.5 text-left transition-colors duration-200"
          :class="point.key === selectedPoint
            ? 'bg-(--sk-ink) text-(--sk-ink-fg)'
            : 'text-(--sk-ink) hover:bg-(--sk-muted-surface)'"
          :aria-pressed="point.key === selectedPoint"
          @click="selectedPoint = point.key"
        >
          <span
            class="size-[7px]"
            :class="point.state ? STATE_DOT[point.state] ?? 'bg-(--sk-ink-subtle)' : 'bg-(--sk-border)'"
            :title="point.state ?? '측정 데이터 없음'"
          />
          <span
            class="truncate font-mono text-xs tabular-nums"
            :class="point.key === selectedPoint ? 'font-semibold' : 'font-medium'"
          >{{ point.key }}</span>
          <span class="font-mono text-xs tabular-nums">{{ point.first }}</span>
        </button>
      </li>
    </ul>

    <p class="flex flex-wrap gap-x-3 gap-y-1 border-t border-(--sk-border-soft) px-4 py-2.5 sk-label">
      <span
        v-for="(dot, state) in STATE_DOT"
        :key="state"
        class="flex items-center gap-1"
      >
        <span
          class="size-[7px]"
          :class="dot"
        />{{ state }}
      </span>
    </p>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  data: AfmDetailRow[]
  availablePoints: string[]
}>()

// The point every card to the right of the rail describes.
const selectedPoint = defineModel<string>('selectedPoint', { required: true })

const dots = computed(() => siteDots(props.data))
const perSite = computed(() => dots.value.length ? Math.round(props.availablePoints.length / dots.value.length) : 0)

const rowsOf = (point: string) => props.data.filter(row => row.measurement_point === point)
const selectedSite = computed(() => {
  const id = rowsOf(selectedPoint.value)[0]?.['Site ID']
  return id == null ? '' : String(id)
})

// Each row previews the first measurement column, so the list reads as values
// down the points rather than as a list of names.
const firstColumn = computed(() => derivePointColumns(props.data).find(c => isMeasurementKey(c.key))?.key ?? '')

const points = computed(() => props.availablePoints.map((key) => {
  const rows = rowsOf(key)
  return {
    key,
    state: pointState(rows),
    first: summaryNumber(rows[0]?.[firstColumn.value])?.toFixed(2) ?? ''
  }
}))
</script>
