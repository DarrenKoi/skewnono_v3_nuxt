<template>
  <div class="dashboard-surface flex flex-wrap items-center gap-x-3 gap-y-2 rounded-(--sk-r-card) px-3 py-2.5">
    <!-- X axis: a CD parameter of the focus MSR. -->
    <div class="flex items-center gap-1.5">
      <span class="sk-eyebrow">X</span>
      <USelect
        :model-value="query.xParam"
        :items="cdParams"
        size="xs"
        class="min-w-[9rem]"
        @update:model-value="patch({ xParam: $event })"
      />
    </div>

    <UIcon
      name="i-lucide-x"
      class="h-3 w-3 text-(--sk-ink-subtle)"
    />

    <!-- Y axis kind: another CD parameter, or a dynamic FDC channel. -->
    <div class="flex items-center gap-1.5">
      <span class="sk-eyebrow">Y</span>
      <div class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5">
        <button
          v-for="opt in yKindOptions"
          :key="opt.value"
          type="button"
          class="rounded-[6px] px-2 py-0.5 font-mono text-[11px] font-medium transition-colors duration-200"
          :class="query.yKind === opt.value
            ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
            : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
          :disabled="opt.value === 'fdc' && fdcParams.length === 0"
          @click="patch({ yKind: opt.value })"
        >
          {{ opt.label }}
        </button>
      </div>
      <USelect
        v-if="query.yKind === 'cd'"
        :model-value="query.yParam"
        :items="cdParams"
        size="xs"
        class="min-w-[9rem]"
        @update:model-value="patch({ yParam: $event })"
      />
      <USelect
        v-else
        :model-value="query.fdcParam"
        :items="fdcParams"
        size="xs"
        class="min-w-[10rem]"
        @update:model-value="patch({ fdcParam: $event })"
      />
    </div>

    <div class="ml-auto flex items-center gap-1.5">
      <span class="sk-eyebrow">그룹</span>
      <USelect
        :model-value="query.group"
        :items="groupItems"
        size="xs"
        class="min-w-[8rem]"
        :disabled="!coordinateReady"
        @update:model-value="patch({ group: $event as FactorQuery['group'] })"
      />
      <UTooltip
        v-if="!coordinateReady"
        text="측정 site 좌표(stage_coordinate)가 없어 반경/섹터 그룹을 사용할 수 없습니다."
      >
        <UIcon
          name="i-lucide-circle-help"
          class="h-3.5 w-3.5 text-(--sk-ink-subtle)"
        />
      </UTooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
// The active query that drives scatter + marginal distribution + group
// distribution + evidence table together.
export interface FactorQuery {
  // Y quantity: another CD parameter, or a per-sequence dynamic FDC channel.
  yKind: 'cd' | 'fdc'
  xParam: string
  yParam: string
  fdcParam: string
  // Radius/sector grouping — ONLY offered when coordinate readiness passes.
  group: 'none' | 'radius' | 'sector'
}

const props = defineProps<{
  cdParams: string[]
  fdcParams: string[]
  coordinateReady: boolean
}>()

const query = defineModel<FactorQuery>({ required: true })

const patch = (part: Partial<FactorQuery>) => {
  query.value = { ...query.value, ...part }
}

const yKindOptions = [
  { value: 'cd' as const, label: 'CD' },
  { value: 'fdc' as const, label: 'FDC' }
]

// Radius/sector grouping is gated on coordinate readiness; when unavailable the
// select is disabled and only '없음' remains meaningful.
const groupItems = computed(() =>
  props.coordinateReady
    ? [
        { label: '없음', value: 'none' },
        { label: '반경(중심→외곽)', value: 'radius' },
        { label: '섹터(방위)', value: 'sector' }
      ]
    : [{ label: '없음', value: 'none' }]
)
</script>
