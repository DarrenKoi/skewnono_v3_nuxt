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
        placeholder="예: ECXDX (장비 일부) 또는 6LD257421"
        size="md"
        :loading="pending"
        :disabled="disabled"
        @update:model-value="emit('update:modelValue', String($event))"
        @keydown.enter="onSearch"
      />
      <UButton
        class="bg-(--sk-ink) text-(--sk-ink-fg)"
        label="Search"
        icon="i-lucide-corner-down-left"
        size="md"
        :loading="pending"
        :disabled="disabled"
        @click="onSearch"
      />
    </div>

    <!-- Fix 4: while facets haven't loaded (still fetching, or the fetch
         failed), the parser has no `known.eq` to match against, so a valid
         equipment id silently misclassifies as a `recipe` substring and
         returns zero rows under a green chip — indistinguishable from a
         genuine no-hit. Disabling the search action here (rather than
         letting it run against a parser that can't recognize eq ids yet) is
         the smaller change than adding a separate warning-banner component,
         and it mirrors FilterBar already going inert on the same signal. -->
    <p
      v-if="disabled"
      class="mt-1.5 text-[11px] text-(--sk-ink-muted)"
    >
      장비 목록을 아직 불러오지 못했습니다 — 계속되면 페이지를 새로고침해 주세요.
    </p>

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
  // True while facets haven't loaded (pending or errored) — see the Fix 4
  // comment below. Blocks the search action so it can't run against a
  // parser with no `known.eq` to check tokens against.
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'search': []
}>()

const onSearch = () => {
  if (props.disabled) return
  emit('search')
}

const LABELS: Record<string, string> = {
  eq: 'EQ',
  lot: 'LOT',
  recipe: 'RECIPE',
  msr: 'MSR',
  date: 'DATE',
  q: 'ANY',
  unknown: '?'
}

const chips = computed(() =>
  (Object.keys(LABELS) as (keyof ParsedQuery)[]).flatMap(field =>
    props.parsed[field].map(value => ({ field, value, label: LABELS[field]! }))
  )
)
</script>
