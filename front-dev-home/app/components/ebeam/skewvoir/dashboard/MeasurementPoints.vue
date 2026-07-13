<template>
  <EbeamSkewvoirPanelFrame
    title="Measurement Points"
    :meta="meta"
    icon="i-lucide-list-ordered"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex h-56 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>
    <div
      v-else-if="points.length"
      class="max-h-72 overflow-auto"
    >
      <table class="w-full border-collapse text-[11.5px]">
        <thead class="sticky top-0 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border-soft) text-left font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
            <th class="px-2 py-1.5 font-medium">
              #
            </th>
            <th class="px-2 py-1.5 font-medium">
              CHIP XY
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              DATA
            </th>
            <th class="px-2 py-1.5 text-right font-medium">
              RADIUS
            </th>
            <th class="px-2 py-1.5 font-medium">
              SEQ
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in points"
            :key="p.key"
            class="border-b border-(--sk-border-soft) last:border-0"
          >
            <td class="px-2 py-1.5 font-mono text-(--sk-ink-subtle)">
              {{ p.mp }}
            </td>
            <td class="px-2 py-1.5 font-mono text-zinc-700 dark:text-zinc-300">
              {{ p.chip }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-zinc-800 dark:text-zinc-100">
              {{ p.cd.toFixed(2) }}
            </td>
            <td class="px-2 py-1.5 text-right font-mono tabular-nums text-(--sk-ink-muted)">
              {{ p.radius.toFixed(2) }}
            </td>
            <td class="px-2 py-1.5 font-mono text-(--sk-ink-subtle)">
              {{ p.seq }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div
      v-else
      class="flex h-56 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      {{ analysis.activeParam.value }} 측정점이 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const points = computed(() =>
  props.analysis.siteRows.value
    .filter(r => r.parameter === props.analysis.activeParam.value && r.mp_number >= 0)
    .map((r, i) => {
      const xy = parseChipXY(r.chip_number)
      return {
        key: `${r.msr}-${r.sequence}-${i}`,
        mp: r.mp_number,
        chip: r.chip_number,
        cd: r.cd_value,
        radius: xy ? Math.hypot(xy[0], xy[1]) : 0,
        seq: r.sequence
      }
    })
)

const meta = computed(() => `${points.value.length} sites · MP: ${props.analysis.activeParam.value}`)
</script>
