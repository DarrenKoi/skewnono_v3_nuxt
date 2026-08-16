<template>
  <!-- Folded by default. MDC history is the evidence you reach for once you
       already suspect a tool, not something read on the way past — and left
       open it puts a six-column table between the trend chart and the bottom of
       the page every single visit. -->
  <details class="group dashboard-surface rounded-[var(--sk-r-card)]">
    <summary
      class="flex cursor-pointer list-none items-center gap-2 px-4 py-3 [&::-webkit-details-marker]:hidden"
    >
      <UIcon
        name="i-lucide-chevron-right"
        class="h-3.5 w-3.5 text-(--sk-ink-muted) transition-transform duration-150 group-open:rotate-90"
      />
      <span class="sk-title">MDC 이력 (빔 조건 × 축)</span>
      <span class="ml-auto sk-meta">{{ caption }}</span>
    </summary>

    <div class="border-t border-(--sk-border-soft) px-4 py-3">
      <table
        v-if="history.length"
        class="w-full text-sm"
      >
        <thead>
          <tr>
            <th class="py-1 text-left sk-label">
              날짜
            </th>
            <th class="py-1 text-left sk-label">
              장비
            </th>
            <th class="py-1 text-left sk-label">
              빔·축
            </th>
            <th class="py-1 text-right sk-label">
              이전
            </th>
            <th class="py-1 text-right sk-label">
              이후
            </th>
            <th class="py-1 text-right sk-label">
              Δ
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(h, i) in sorted"
            :key="i"
            class="border-t border-(--sk-border-soft)"
          >
            <td class="py-1 font-mono text-xs tabular-nums text-(--sk-ink-muted)">
              {{ h.date }}
            </td>
            <td class="py-1 font-mono text-xs text-(--sk-ink)">
              {{ h.eqp_id }}
            </td>
            <td class="py-1 text-xs text-(--sk-ink-muted)">
              {{ h.beam_condition }} · {{ h.axis }}
            </td>
            <td class="py-1 text-right font-mono text-xs tabular-nums text-(--sk-ink-muted)">
              {{ h.old_value.toFixed(4) }}
            </td>
            <td class="py-1 text-right font-mono text-xs tabular-nums text-(--sk-ink)">
              {{ h.new_value.toFixed(4) }}
            </td>
            <td
              class="py-1 text-right font-mono text-xs tabular-nums"
              :style="{ color: h.new_value - h.old_value >= 0 ? 'var(--sk-ok)' : 'var(--sk-bad)' }"
            >
              {{ (h.new_value - h.old_value >= 0 ? '+' : '') + (h.new_value - h.old_value).toFixed(4) }}
            </td>
          </tr>
        </tbody>
      </table>
      <p
        v-else
        class="sk-body text-(--sk-ink-muted)"
      >
        기록된 MDC 변경이 없습니다.
      </p>
    </div>
  </details>
</template>

<script setup lang="ts">
import type { MdcHistoryEntry } from '~/composables/useTttmApi'

const props = defineProps<{ history: MdcHistoryEntry[] }>()
const sorted = computed(() => [...props.history].sort((a, b) => b.date.localeCompare(a.date)))

// The summary has to say enough to decide whether opening is worth it, so it
// names the tools involved rather than only counting rows.
const caption = computed(() => {
  if (!props.history.length) return '변경 없음'
  const tools = [...new Set(props.history.map(h => h.eqp_id))]
  const named = tools.length <= 2 ? tools.join(' · ') : `장비 ${tools.length}대`
  return `${named} · ${props.history.length}건`
})
</script>
