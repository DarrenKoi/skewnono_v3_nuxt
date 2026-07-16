<template>
  <div class="dashboard-surface flex flex-wrap items-center gap-x-3 gap-y-2 rounded-(--sk-r-card) px-3 py-2.5">
    <!-- 이상·실패 우선: evidence-backed only (failure/residual, NOT vendor score). -->
    <button
      type="button"
      class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) border px-2.5 py-1 font-mono text-[11px] font-medium transition-colors duration-200"
      :class="model.evidenceOnly
        ? 'border-(--sk-bad)/40 bg-(--sk-bad)/10 text-(--sk-bad)'
        : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
      @click="patch({ evidenceOnly: !model.evidenceOnly })"
    >
      <UIcon
        name="i-lucide-triangle-alert"
        class="h-3.5 w-3.5"
      />
      이상·실패 우선
    </button>

    <!-- Image-present filter. -->
    <button
      type="button"
      class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) border px-2.5 py-1 font-mono text-[11px] font-medium transition-colors duration-200"
      :class="model.imageOnly
        ? 'border-(--sk-accent)/40 bg-(--sk-accent)/10 text-(--sk-accent)'
        : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
      @click="patch({ imageOnly: !model.imageOnly })"
    >
      <UIcon
        name="i-lucide-image"
        class="h-3.5 w-3.5"
      />
      이미지 있음
    </button>

    <div class="h-4 w-px bg-(--sk-border)" />

    <!-- Chip / sequence search. -->
    <div class="relative min-w-[9rem] flex-1">
      <UIcon
        name="i-lucide-search"
        class="pointer-events-none absolute top-1/2 left-2 h-3.5 w-3.5 -translate-y-1/2 text-(--sk-ink-subtle)"
      />
      <input
        :value="model.query"
        type="text"
        placeholder="chip / sequence 검색"
        class="w-full rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-surface) py-1 pr-2 pl-7 font-mono text-[11px] text-(--sk-ink) placeholder:text-(--sk-ink-subtle) focus:border-(--sk-accent) focus:outline-none"
        @input="patch({ query: ($event.target as HTMLInputElement).value })"
      >
    </div>

    <!-- Count summary — separates evidence from the vendor monitoring badge. -->
    <div class="flex items-center gap-2 font-mono text-[11px] text-(--sk-ink-muted)">
      <span>{{ counts.shown }}/{{ counts.total }}</span>
      <span
        v-if="counts.failure"
        class="text-(--sk-bad)"
      >실패 {{ counts.failure }}</span>
      <span
        v-if="counts.residual"
        class="text-(--sk-warn)"
      >잔차 {{ counts.residual }}</span>
      <span
        v-if="counts.monitor"
        class="text-(--sk-ink-subtle)"
      >모니터링 {{ counts.monitor }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface ReviewFilter {
  evidenceOnly: boolean
  imageOnly: boolean
  query: string
}

const props = defineProps<{
  modelValue: ReviewFilter
  counts: { total: number, shown: number, failure: number, residual: number, monitor: number }
}>()
const emit = defineEmits<{ 'update:modelValue': [value: ReviewFilter] }>()

const model = computed(() => props.modelValue)
const patch = (part: Partial<ReviewFilter>) => emit('update:modelValue', { ...props.modelValue, ...part })
</script>
