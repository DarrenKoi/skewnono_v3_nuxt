<template>
  <AfmCard
    icon="i-lucide-info"
    title="측정 정보"
  >
    <dl class="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
      <div
        v-for="(value, key) in information"
        :key="key"
        class="flex items-baseline justify-between gap-3 border-b border-(--sk-border-soft) pb-1.5"
      >
        <dt class="sk-label">
          {{ key }}
        </dt>
        <dd class="truncate text-right sk-value-num">
          {{ value === null || value === '' ? '–' : value }}
        </dd>
      </div>
    </dl>

    <div
      v-if="meanRows.length"
      class="mt-5"
    >
      <p class="mb-2 sk-label">
        사이트별 요약 (MEAN)
      </p>
      <div class="overflow-x-auto rounded-(--sk-r-chip) border border-(--sk-border)">
        <table class="w-full">
          <thead>
            <tr class="border-b border-(--sk-border)">
              <th class="px-2 py-1.5 text-left sk-label">
                Site
              </th>
              <th
                v-for="col in columns"
                :key="col"
                class="px-2 py-1.5 text-right sk-label"
              >
                {{ col }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-(--sk-border-soft)">
            <tr
              v-for="row in meanRows"
              :key="row.Site"
            >
              <td class="px-2 py-1 text-left sk-value-num">
                {{ row.Site }}
              </td>
              <td
                v-for="col in columns"
                :key="col"
                class="px-2 py-1 text-right sk-value-num"
              >
                {{ summaryNumber(row[col])?.toFixed(2) ?? '–' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmInformation, AfmSummaryRow } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  information: AfmInformation
  summary: AfmSummaryRow[]
}>()

const columns = computed(() => summaryColumns(props.summary))
const meanRows = computed(() => props.summary.filter(row => row.ITEM === 'MEAN'))
</script>
