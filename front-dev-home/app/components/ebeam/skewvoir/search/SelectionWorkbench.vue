<template>
  <section class="dashboard-surface flex min-w-0 flex-col rounded-(--sk-r-card) p-3">
    <header class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            측정 작업 세트
          </h2>
          <span class="rounded-(--sk-r-chip) bg-(--sk-brand-soft) px-1.5 py-0.5 font-mono text-[10px] font-semibold text-(--sk-brand)">
            {{ selected.length }}
          </span>
        </div>
        <p class="mt-1 truncate font-mono text-[9.5px] text-(--sk-ink-subtle)">
          {{ coverage.recipes }} RECIPE · {{ coverage.lots }} LOT · {{ coverage.equipment }} EQ
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-1.5">
        <span
          v-if="selected.length > 30"
          class="font-mono text-[9px] text-(--sk-bad)"
        >최대 30개 표시</span>
        <UButton
          color="primary"
          variant="solid"
          size="sm"
          icon="i-lucide-trending-up"
          label="Time-Series"
          :disabled="!selected.length"
          @click="emit('analyze')"
        />
        <UButton
          v-if="selected.length"
          color="neutral"
          variant="ghost"
          size="sm"
          icon="i-lucide-trash-2"
          aria-label="선택 비우기"
          @click="emit('clear')"
        />
      </div>
    </header>

    <div class="mt-3 flex min-h-12 max-h-28 min-w-0 flex-1 flex-wrap content-start items-start gap-1.5 overflow-y-auto border-t border-(--sk-border-soft) pt-2.5">
      <p
        v-if="!selected.length"
        class="self-center text-[11.5px] text-(--sk-ink-muted)"
      >
        검색 결과의 체크박스로 여러 검색의 측정을 모으세요.
      </p>
      <span
        v-for="row in selected"
        v-else
        :key="row.msr"
        class="group inline-flex max-w-56 shrink-0 items-center gap-1 rounded-(--sk-r-chip) bg-(--sk-chip-bg) py-1 pl-2 pr-1 font-mono text-[9.5px] text-(--sk-ink)"
        :title="`${row.full_name} · ${row.lot_id} · ${row.eqp_id}`"
      >
        <span class="truncate">{{ row.lot_id }} · {{ row.eqp_id }}</span>
        <button
          type="button"
          class="rounded p-0.5 text-(--sk-ink-subtle) transition hover:bg-(--sk-bad)/10 hover:text-(--sk-bad)"
          :aria-label="`${row.full_name} 선택 제거`"
          @click="emit('remove', row.msr)"
        >
          <UIcon
            name="i-lucide-x"
            class="h-3 w-3"
          />
        </button>
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { MeasHistRow } from '~/composables/useMeasHistApi'
import { summarizeSelectionCoverage } from '~/utils/skewvoirSearchUi'

const props = defineProps<{
  selected: MeasHistRow[]
}>()

const emit = defineEmits<{
  remove: [msr: string]
  clear: []
  analyze: []
}>()

const coverage = computed(() => summarizeSelectionCoverage(props.selected))
</script>
