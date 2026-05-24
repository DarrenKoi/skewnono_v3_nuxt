<template>
  <div class="min-h-0 flex-1 overflow-auto">
    <table class="w-full border-collapse font-mono text-[11.5px]">
      <thead>
        <tr class="sticky top-0 z-10 bg-zinc-50/80 text-left text-zinc-500 dark:bg-zinc-900/60 dark:text-zinc-400">
          <th
            v-for="col in columns"
            :key="col"
            class="border-b border-zinc-200 px-2.5 py-1.5 font-medium tracking-wide whitespace-nowrap dark:border-zinc-800"
          >
            {{ col }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, i) in rows"
          :key="i"
        >
          <td
            v-for="col in columns"
            :key="col"
            class="border-b border-zinc-100 px-2.5 py-1 whitespace-nowrap text-zinc-800 dark:border-zinc-800/60 dark:text-zinc-200"
          >
            <template v-if="col === 'Diff' || col === 'Rel'">
              <EbeamRecipeOpenBoolPill
                :value="row[col]"
                :ok-when="false"
              />
            </template>
            <template v-else>
              {{ row[col] }}
            </template>
          </td>
        </tr>
        <tr v-if="rows.length === 0">
          <td
            :colspan="columns.length"
            class="px-3 py-4 text-center text-[12px] text-(--sk-ink-muted)"
          >
            매칭되는 측정 포인트가 없습니다.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import type { WaferMpInfoRow } from '~/composables/useRecipeSearchApi'

type MpColumn = keyof WaferMpInfoRow

withDefaults(defineProps<{
  rows: WaferMpInfoRow[]
  columns?: readonly MpColumn[]
}>(), {
  columns: () => [
    'ChipNo_X', 'ChipNo_Y',
    'Coordinate_X', 'Coordinate_Y',
    'P_No', 'D_No',
    'Diff', 'Rel',
    'Rel_MoveX', 'RelMoveY',
    'img_meas2'
  ]
})
</script>
