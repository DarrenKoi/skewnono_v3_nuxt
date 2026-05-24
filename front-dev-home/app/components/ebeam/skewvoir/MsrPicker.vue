<template>
  <section class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <UInput
        v-model="query"
        size="xs"
        icon="i-lucide-search"
        placeholder="recipe / lot / eqp / msr 검색"
        class="min-w-[16rem] flex-1"
      />
      <UButton
        size="xs"
        color="neutral"
        variant="outline"
        :label="`보이는 ${filtered.length}건 선택`"
        @click="selectAllVisible"
      />
      <UButton
        size="xs"
        color="neutral"
        variant="ghost"
        label="선택 해제"
        :disabled="modelValue.length === 0"
        @click="clearSelection"
      />
      <span class="ml-auto font-mono text-[11px] tabular-nums text-(--sk-ink-muted)">
        {{ modelValue.length }} / {{ rows.length }} 선택
      </span>
    </div>

    <UTable
      class="font-mono-ids"
      :columns="columns"
      :data="visible"
      sticky="header"
      :ui="tableUi"
    >
      <template #select-header>
        <UCheckbox
          :model-value="allVisibleSelected"
          size="xs"
          @update:model-value="toggleAllVisible"
        />
      </template>
      <template #select-cell="{ row }">
        <UCheckbox
          :model-value="selectedSet.has(row.original.msr)"
          size="xs"
          @update:model-value="toggleRow(row.original.msr)"
        />
      </template>

      <template #timestamp-cell="{ row }">
        <span class="font-mono text-[11.5px] tabular-nums text-zinc-700 dark:text-zinc-200">
          {{ formatTimestamp(row.original.timestamp) }}
        </span>
      </template>
      <template #eqp_id-cell="{ row }">
        <span class="font-mono text-[12px] font-semibold text-zinc-900 dark:text-zinc-100">
          {{ row.original.eqp_id }}
        </span>
      </template>
      <template #lot_id-cell="{ row }">
        <span class="font-mono text-[11.5px] text-zinc-700 dark:text-zinc-200">{{ row.original.lot_id }}</span>
      </template>
      <template #recipe_name-cell="{ row }">
        <span class="font-mono text-[11.5px] text-zinc-700 dark:text-zinc-200">{{ row.original.recipe_name }}</span>
      </template>
      <template #msr_check-cell="{ row }">
        <UBadge
          :label="row.original.msr_check"
          :color="row.original.msr_check === 'Yes' ? 'success' : 'error'"
          size="xs"
          variant="subtle"
        />
      </template>
      <template #align_fail-cell="{ row }">
        <UBadge
          :label="row.original.align_fail"
          :color="row.original.align_fail === 'Pass' ? 'success' : row.original.align_fail === 'Fail' ? 'error' : 'neutral'"
          size="xs"
          variant="subtle"
        />
      </template>
    </UTable>

    <p
      v-if="filtered.length > visibleLimit"
      class="mt-2 text-center font-mono text-[10.5px] text-zinc-400"
    >
      {{ visibleLimit }} / {{ filtered.length }}건 표시 — 검색으로 좁혀 보세요.
    </p>
  </section>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { MeasHistRow } from '~/composables/useMeasHistApi'
import { formatRecipeTimestamp, recipeTableUi } from '~/utils/recipeView'

const props = defineProps<{
  rows: MeasHistRow[]
  modelValue: string[]
}>()

const emit = defineEmits<{ 'update:modelValue': [string[]] }>()

const visibleLimit = 200
const query = ref('')

const selectedSet = computed(() => new Set(props.modelValue))

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter(r =>
    r.recipe_name.toLowerCase().includes(q)
    || r.lot_id.toLowerCase().includes(q)
    || r.eqp_id.toLowerCase().includes(q)
    || r.msr.toLowerCase().includes(q)
    || r.class_name.toLowerCase().includes(q)
  )
})

const visible = computed(() => filtered.value.slice(0, visibleLimit))

const allVisibleSelected = computed(() =>
  visible.value.length > 0 && visible.value.every(r => selectedSet.value.has(r.msr))
)

const toggleRow = (msr: string) => {
  const next = new Set(props.modelValue)
  if (next.has(msr)) next.delete(msr)
  else next.add(msr)
  emit('update:modelValue', [...next])
}

const toggleAllVisible = () => {
  if (allVisibleSelected.value) {
    const visibleMsrs = new Set(visible.value.map(r => r.msr))
    emit('update:modelValue', props.modelValue.filter(msr => !visibleMsrs.has(msr)))
  } else {
    selectAllVisible()
  }
}

const selectAllVisible = () => {
  const next = new Set(props.modelValue)
  for (const r of visible.value) next.add(r.msr)
  emit('update:modelValue', [...next])
}

const clearSelection = () => emit('update:modelValue', [])

const formatTimestamp = (iso: string) => formatRecipeTimestamp(iso)

const columns: TableColumn<MeasHistRow>[] = [
  { id: 'select', header: '', size: 36 },
  { accessorKey: 'timestamp', header: 'timestamp', size: 138 },
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 110 },
  { accessorKey: 'lot_id', header: 'lot_id', size: 132 },
  { accessorKey: 'class_name', header: 'class', size: 72 },
  { accessorKey: 'recipe_name', header: 'recipe', size: 240 },
  { accessorKey: 'msr_check', header: 'msr', size: 70 },
  { accessorKey: 'align_fail', header: 'align', size: 78 }
]

const tableUi = recipeTableUi
</script>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
