<template>
  <section class="dashboard-surface flex flex-col rounded-(--sk-r-card)">
    <!-- Panel header: title + optional meta, with an inline segmented toggle and
         an actions slot on the right (matches the sample's panel chrome). -->
    <header class="flex items-center justify-between gap-2 border-b border-(--sk-border-soft) px-3 py-2.5">
      <div class="flex min-w-0 items-baseline gap-2">
        <h2
          class="truncate"
          :class="titleSize === 'md' ? 'sk-panel-title' : 'sk-title'"
        >
          {{ title }}
        </h2>
        <span
          v-if="meta"
          class="truncate sk-meta"
        >{{ meta }}</span>
      </div>

      <div class="flex shrink-0 items-center gap-1.5">
        <div
          v-if="toggles?.length"
          class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
        >
          <button
            v-for="opt in toggles"
            :key="opt"
            type="button"
            class="rounded-[6px] px-2.5 py-1 font-mono text-xs font-medium transition-colors duration-200"
            :class="opt === active
              ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
              : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
            @click="select(opt)"
          >
            {{ opt }}
          </button>
        </div>
        <slot name="actions" />
      </div>
    </header>

    <!-- Body. Falls back to a dashed placeholder when no content is provided
         (this pass ships structure only; the chart-wiring pass fills the slot). -->
    <div
      class="min-h-0 flex-1 p-3"
      :class="bodyClass"
    >
      <slot :active="active">
        <div
          class="flex h-full items-center justify-center rounded-(--sk-r-chip) border border-dashed border-(--sk-border) text-(--sk-ink-subtle)"
          :class="placeholderHeight"
        >
          <UIcon
            :name="icon"
            class="h-7 w-7"
          />
        </div>
      </slot>
    </div>
  </section>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  title: string
  meta?: string
  /** Segmented toggle options (e.g. ['Cell','Dot']). First is active by default. */
  toggles?: string[]
  /** Controlled active toggle (v-model). Omit for uncontrolled internal state. */
  modelValue?: string
  /** Title tier. `sm` (13px, `.sk-title`) is the default because most callers
   *  are cells in a dense multi-column grid — the 측정 개요 dashboard packs
   *  Wafer Map / 파라미터 요약 / Measurement Points / SEM Image / Radius into
   *  one row, and at 16px those headings truncate to "Wafer …" / "Measure…".
   *  `md` (16px, `.sk-panel-title`) is for panels that own the full width, where
   *  13px left the heading smaller than the labels inside the panel. */
  titleSize?: 'sm' | 'md'
  /** Placeholder icon shown when the default body slot is empty. */
  icon?: string
  /** Min-height utility for the placeholder body, e.g. 'min-h-48'. */
  placeholderHeight?: string
  bodyClass?: string
}>(), {
  titleSize: 'sm',
  icon: 'i-lucide-bar-chart-3',
  placeholderHeight: 'min-h-40'
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

// Uncontrolled fallback so a bare <PanelFrame :toggles="..."> still toggles.
const internal = ref(props.toggles?.[0])

const active = computed(() => props.modelValue ?? internal.value)

const select = (opt: string) => {
  internal.value = opt
  emit('update:modelValue', opt)
}
</script>
