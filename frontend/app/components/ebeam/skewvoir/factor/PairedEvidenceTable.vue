<template>
  <div class="max-h-64 overflow-auto">
    <table class="w-full border-collapse text-xs">
      <thead class="sticky top-0 z-10 bg-(--sk-surface)">
        <tr class="border-b border-(--sk-border) font-mono text-[11px] text-(--sk-ink-muted)">
          <th
            scope="col"
            class="px-1.5 py-1.5 text-left font-semibold"
          >
            SITE
          </th>
          <th
            scope="col"
            class="px-1.5 py-1.5 text-right font-semibold"
          >
            SEQ
          </th>
          <th
            scope="col"
            class="px-1.5 py-1.5 text-right font-semibold"
          >
            {{ xLabel }}
          </th>
          <th
            scope="col"
            class="px-1.5 py-1.5 text-right font-semibold"
          >
            {{ yLabel }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="p in points"
          :key="p.key"
          class="cursor-pointer border-b border-(--sk-border-soft) transition-colors duration-200 last:border-0"
          :class="p.chip === focusedSite ? 'bg-(--sk-brand)/15' : 'hover:bg-(--sk-chip-bg)'"
          @click="emit('focus', p.chip)"
        >
          <td class="px-1.5 py-1.5 font-mono">
            {{ p.chip }}
          </td>
          <td class="px-1.5 py-1.5 text-right font-mono tabular-nums">
            {{ p.sequence }}
          </td>
          <td class="px-1.5 py-1.5 text-right font-mono font-medium tabular-nums">
            {{ p.x.toFixed(3) }}
          </td>
          <td class="px-1.5 py-1.5 text-right font-mono font-medium tabular-nums">
            {{ p.y.toFixed(3) }}
          </td>
        </tr>
        <tr v-if="points.length === 0">
          <td
            colspan="4"
            class="px-1.5 py-6 text-center text-(--sk-ink-subtle)"
          >
            짝지어진 관측치가 없습니다.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import type { PairedPoint } from '~/utils/skewvoirAnalysis/relationships'

defineProps<{
  points: PairedPoint[]
  xLabel: string
  yLabel: string
  focusedSite: string | null
}>()

const emit = defineEmits<{ focus: [chip: string] }>()
</script>
