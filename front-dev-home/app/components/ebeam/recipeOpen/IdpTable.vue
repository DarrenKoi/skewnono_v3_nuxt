<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
    <div class="flex items-start justify-between gap-3 border-b border-zinc-200/70 px-4 py-3 dark:border-zinc-800/70">
      <div>
        <p class="sk-eyebrow text-(--sk-brand)">
          IDP_IMAGE_INFO
        </p>
        <p class="mt-0.5 sk-title">
          파라미터 목록 · {{ rows.length }}
        </p>
      </div>
      <div class="flex flex-col items-end gap-1.5">
        <span class="sk-meta">
          행 클릭 → 우측 상세 표시
        </span>
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-eye"
          label="Align 정보"
          class="rounded-lg font-semibold"
          @click="$emit('openAlign')"
        />
      </div>
    </div>
    <div class="min-h-0 flex-1 overflow-auto">
      <table class="w-full border-collapse font-mono text-[12px]">
        <thead>
          <tr class="sticky top-0 z-10 bg-zinc-50/80 text-left text-(--sk-ink-muted) dark:bg-zinc-900/60">
            <th class="w-1 p-0" />
            <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800">
              Parameter
            </th>
            <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800">
              SEQ
            </th>
            <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800">
              Region
            </th>
            <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800">
              Addressing
            </th>
            <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800">
              Mother
            </th>
            <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800">
              Double
            </th>
            <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800">
              Cnt
            </th>
            <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-medium tracking-wide dark:border-zinc-800">
              d#_rm
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in rows"
            :key="`${row.Parameter}-${row.SEQ}`"
            class="cursor-pointer transition-colors"
            :class="index === selectedIndex
              ? 'bg-(--sk-brand-soft)/55'
              : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/40'"
            @click="selectedIndex = index"
          >
            <td
              class="w-1 p-0"
              :class="index === selectedIndex ? 'bg-(--sk-brand)' : ''"
            />
            <td
              class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-900 dark:border-zinc-800/60 dark:text-zinc-100"
              :class="index === selectedIndex ? 'font-bold' : 'font-semibold'"
            >
              {{ row.Parameter }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-600 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ row.SEQ }}/{{ row.Last_SEQ }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-600 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ row.Region }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 dark:border-zinc-800/60">
              <EbeamRecipeOpenYesNoPill :value="row.Addressing" />
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-600 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ row.Mother_Para }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 dark:border-zinc-800/60">
              <EbeamRecipeOpenBoolPill :value="row.Double_Addressing" />
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-600 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ row.Meas_Counting }}
            </td>
            <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-1.5 text-zinc-600 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ row.dnumber_removed }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IdpImageInfoRow } from '~/composables/useRecipeSearchApi'

defineProps<{
  rows: IdpImageInfoRow[]
}>()

defineEmits<{
  openAlign: []
}>()

const selectedIndex = defineModel<number>('selectedIndex', { required: true })
</script>
