<template>
  <section
    class="dashboard-surface space-y-3 rounded-(--sk-r-card) px-4 py-3"
    aria-label="포인트 분석"
  >
    <div class="flex flex-wrap items-center gap-x-6 gap-y-3">
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-crosshair"
          class="size-[18px] text-(--sk-ink-muted)"
        />
        <h2 class="sk-panel-title">
          포인트 분석
        </h2>
        <UBadge
          :label="String(points.length)"
          color="neutral"
          variant="subtle"
          class="font-mono tabular-nums"
        />
      </div>

      <template v-if="selectedPoint">
        <div class="flex min-w-0 items-center gap-2">
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-chevron-left"
            aria-label="이전 포인트"
            :disabled="index <= 0"
            @click="step(-1)"
          />
          <span class="min-w-0 truncate sk-card-id">{{ selectedPoint }}</span>
          <span class="font-mono text-[13px] text-(--sk-ink-muted) tabular-nums">
            {{ index + 1 }} / {{ points.length }}
          </span>
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-chevron-right"
            aria-label="다음 포인트"
            :disabled="index >= points.length - 1"
            @click="step(1)"
          />
        </div>

        <dl
          v-if="facts.length"
          class="flex flex-wrap items-baseline gap-x-4 gap-y-1"
        >
          <div
            v-for="fact in facts"
            :key="fact.label"
            class="flex items-baseline gap-1.5"
          >
            <dt class="text-xs text-(--sk-ink-muted)">
              {{ fact.label }}
            </dt>
            <dd class="font-mono text-[13px] font-semibold tabular-nums text-(--sk-ink)">
              {{ fact.value }}
            </dd>
          </div>
        </dl>
      </template>

      <p class="ml-auto sk-meta">
        분포 · 히트맵 · 프로파일 이미지가 이 포인트로 그려집니다.
      </p>
    </div>

    <p
      v-if="!points.length"
      class="py-2 sk-body"
    >
      측정 포인트가 없습니다.
    </p>
    <div
      v-else
      class="flex max-h-[7.5rem] flex-wrap gap-1.5 overflow-y-auto"
      role="group"
      aria-label="포인트 선택"
    >
      <SkChip
        v-for="point in points"
        :key="point"
        size="sm"
        tone="ink"
        :label="point"
        :active="selectedPoint === point"
        @click="selectedPoint = point"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
// The picker for everything point-scoped on 측정 상세. It heads the three point
// cards (분포, 히트맵, 프로파일 이미지) instead of sitting inside the points table,
// so the control and what it changes read as one block. The pick is a subject
// among peers, so the chips take the ink tone (DESIGN.md §Selection Primitives).
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  points: string[]
  data: AfmDetailRow[]
}>()

const selectedPoint = defineModel<string>({ required: true })

const index = computed(() => props.points.indexOf(selectedPoint.value))

const step = (delta: number) => {
  const next = props.points[index.value + delta]
  if (next) selectedPoint.value = next
}

const formatCoord = (value: unknown) =>
  typeof value === 'number' ? (Number.isInteger(value) ? String(value) : value.toFixed(2)) : undefined

// The point's own row, where the file has one (some files carry no Data table).
const facts = computed(() => {
  const rows = props.data.filter(row => row.measurement_point === selectedPoint.value)
  const row = rows[0]
  if (!row) return []
  const valid = rows.filter(r => r.Valid === true).length
  return [
    { label: '#', value: formatCoord(row['Point No']) },
    { label: 'X (μm)', value: formatCoord(row['X (um)']) },
    { label: 'Y (μm)', value: formatCoord(row['Y (um)']) },
    { label: '상태', value: row.State ? String(row.State) : undefined },
    { label: '유효', value: `${valid} / ${rows.length}` }
  ].filter((fact): fact is { label: string, value: string } => fact.value !== undefined)
})
</script>
