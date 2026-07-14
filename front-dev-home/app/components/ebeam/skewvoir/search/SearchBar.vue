<template>
  <div>
    <p class="mb-2 px-0.5 text-[11px] text-(--sk-ink-muted)">
      검색 · <span class="font-semibold text-zinc-600 dark:text-zinc-300">장비 / Recipe / Lot / 날짜 / MSR</span>
      · OpenSearch<span v-if="retentionDays"> · 최근 {{ retentionDays }}일 보존</span>
    </p>
    <div class="flex items-center gap-2">
      <UInput
        :model-value="modelValue"
        class="flex-1"
        icon="i-lucide-search"
        placeholder="ECXDX925, 6LD257421, ADI_CD_BIAS_001, 2026-05-10 …"
        size="md"
        :loading="pending"
        @update:model-value="emit('update:modelValue', String($event))"
        @keydown.enter="emit('search')"
      />
      <UButton
        class="bg-(--sk-ink) text-(--sk-ink-fg)"
        label="Search"
        icon="i-lucide-corner-down-left"
        size="md"
        :loading="pending"
        @click="emit('search')"
      />
    </div>

    <!-- How each token was read. Without this, auto-detection is a black box
         and a typo is indistinguishable from a genuine no-hit. -->
    <div
      v-if="chips.length"
      class="mt-2 flex flex-wrap items-center gap-1.5"
    >
      <span
        v-for="chip in chips"
        :key="`${chip.field}:${chip.value}`"
        class="inline-flex h-6 items-center gap-1 rounded-(--sk-r-chip) px-2 font-mono text-[11px]"
        :class="chip.field === 'unknown'
          ? 'bg-(--sk-bad)/10 text-(--sk-bad)'
          : 'bg-(--sk-chip-bg) text-(--sk-chip-text)'"
      >
        <span class="opacity-60">{{ chip.label }}</span>
        {{ chip.value }}
        <button
          type="button"
          class="opacity-60 hover:opacity-100"
          @click="emit('update:modelValue', removeToken(modelValue, chip.value))"
        >
          <UIcon
            name="i-lucide-x"
            class="h-3 w-3"
          />
        </button>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ParsedQuery } from '~/utils/measHistQuery'
import { removeToken } from '~/utils/measHistQuery'

const props = defineProps<{
  modelValue: string
  parsed: ParsedQuery
  pending?: boolean
  // Optional: when the caller has the facets response in hand, show the
  // retention window next to the search hint. Omitted, the hint just drops
  // that segment rather than lying with a stale/hardcoded day count.
  retentionDays?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'search': []
}>()

const LABELS: Record<string, string> = {
  eq: 'EQ',
  lot: 'LOT',
  recipe: 'RECIPE',
  msr: 'MSR',
  date: 'DATE',
  unknown: '?'
}

const chips = computed(() =>
  (Object.keys(LABELS) as (keyof ParsedQuery)[]).flatMap(field =>
    props.parsed[field].map(value => ({ field, value, label: LABELS[field]! }))
  )
)
</script>
