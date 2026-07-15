<template>
  <USlideover
    :open="open"
    :title="lotCd ?? ''"
    :description="bucketLabel"
    :ui="{ content: 'w-[80vw] sm:max-w-[80vw]' }"
    @update:open="(value: boolean) => emit('update:open', value)"
  >
    <template #body>
      <div class="space-y-3">
        <div
          v-if="summaryRow"
          class="rounded-2xl bg-zinc-50 px-3.5 py-3 ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="sk-eyebrow">
                {{ text.summaryHeading }}
              </p>
              <p class="mt-0.5 sk-value">
                {{ summaryRow.ctn_desc || '—' }}
              </p>
            </div>
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              icon="i-lucide-download"
              :label="text.csv"
              :disabled="recipeRows.length === 0"
              @click="onDownloadCsv"
            />
          </div>
          <dl class="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px] sm:grid-cols-4">
            <div>
              <dt class="sk-label">
                fac_id
              </dt>
              <dd class="sk-value-num">
                {{ summaryRow.fac_id }}
              </dd>
            </div>
            <div>
              <dt class="sk-label">
                avail_recipe
              </dt>
              <dd class="sk-value-num">
                {{ summaryRow.avail_recipe }} / {{ summaryRow.total_recipe }}
              </dd>
            </div>
            <div>
              <dt class="sk-label">
                para_all
              </dt>
              <dd class="sk-value-num">
                {{ summaryRow.para_all }}
              </dd>
            </div>
            <div>
              <dt class="sk-label">
                stack
              </dt>
              <dd class="sk-value-num">
                {{ summaryRow.para_16 }}/{{ summaryRow.para_13 }}/{{ summaryRow.para_9 }}/{{ summaryRow.para_5 }}
              </dd>
            </div>
          </dl>
        </div>

        <div
          v-if="recipeRows.length === 0"
          class="rounded-2xl px-4 py-12 text-center sk-body ring-1 ring-zinc-200 dark:ring-zinc-800"
        >
          {{ text.empty }}
        </div>
        <UTable
          v-else
          class="font-mono-ids"
          :columns="columns"
          :data="recipeRows"
          :meta="tableMeta"
          sticky="header"
        />
      </div>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { RecipeInfoRow, SummaryRow } from '~/composables/useRecipeStatisticsApi'
import { downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{
  open: boolean
  lotCd: string | null
  bucketKey: string
  bucketLabel: string
  date: string | null
  summaryRow: SummaryRow | null
  recipeRows: RecipeInfoRow[]
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const text = {
  summaryHeading: '디바이스 요약',
  empty: '이 버킷에는 상세 레시피가 없습니다.',
  csv: 'CSV 다운로드'
} as const

const csvFields = [
  'lot_cd', 'fac_id', 'oper_seq', 'oper_id', 'oper_desc', 'recipe_id',
  'eqp_id', 'samp_seq', 'skip_yn', 'chg_tm', 'ctn_desc',
  'para_all', 'para_16', 'para_13', 'para_9', 'para_5',
  'para_16_percent', 'para_13_percent', 'para_9_percent', 'para_5_percent'
] as const satisfies readonly (keyof RecipeInfoRow)[]

const onDownloadCsv = () => {
  if (!props.lotCd || props.recipeRows.length === 0) return
  const dateTag = props.date ?? new Date().toISOString().slice(0, 10)
  const bucketTag = props.bucketKey.replace(/_summary$/, '')
  const filename = `recipe-${props.lotCd}-${bucketTag}-${dateTag}.csv`
  const rows = props.recipeRows.map(row => csvFields.map(field => row[field]))
  downloadCsv(filename, [...csvFields], rows)
}

const columns: TableColumn<RecipeInfoRow>[] = [
  { accessorKey: 'oper_seq', header: 'seq', size: 56 },
  { accessorKey: 'oper_id', header: 'oper_id', size: 96 },
  { accessorKey: 'recipe_id', header: 'recipe_id', size: 176 },
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 88 },
  { accessorKey: 'samp_seq', header: 'samp', size: 56 },
  { accessorKey: 'skip_yn', header: 'skip', size: 56 },
  { accessorKey: 'para_all', header: 'para_all', size: 80 },
  { accessorKey: 'para_16', header: 'para_16', size: 72 },
  { accessorKey: 'para_13', header: 'para_13', size: 72 },
  { accessorKey: 'para_9', header: 'para_9', size: 64 },
  { accessorKey: 'para_5', header: 'para_5', size: 64 }
]

const tableMeta = {
  class: {
    tr: 'select-none transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
    th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}
</script>
