<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">
      MDC 이력 (빔 조건 × 축)
    </p>
    <table
      v-if="history.length"
      class="mt-3 w-full text-sm"
    >
      <thead>
        <tr class="text-(--sk-ink-muted) text-xs">
          <th class="text-left font-normal py-1">
            날짜
          </th>
          <th class="text-left font-normal py-1">
            장비
          </th>
          <th class="text-left font-normal py-1">
            빔·축
          </th>
          <th class="text-right font-normal py-1">
            이전
          </th>
          <th class="text-right font-normal py-1">
            이후
          </th>
          <th class="text-right font-normal py-1">
            Δ
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(h, i) in sorted"
          :key="i"
          class="border-t"
          :style="{ borderColor: 'var(--sk-border-soft)' }"
        >
          <td class="py-1 tabular-nums text-(--sk-ink-muted)">
            {{ h.date }}
          </td>
          <td class="py-1 text-(--sk-ink)">
            {{ h.eqp_id }}
          </td>
          <td class="py-1 text-(--sk-ink-muted)">
            {{ h.beam_condition }} · {{ h.axis }}
          </td>
          <td class="py-1 text-right tabular-nums text-(--sk-ink-muted)">
            {{ h.old_value.toFixed(4) }}
          </td>
          <td class="py-1 text-right tabular-nums text-(--sk-ink)">
            {{ h.new_value.toFixed(4) }}
          </td>
          <td
            class="py-1 text-right tabular-nums"
            :style="{ color: h.new_value - h.old_value >= 0 ? 'var(--sk-ok)' : 'var(--sk-bad)' }"
          >
            {{ (h.new_value - h.old_value >= 0 ? '+' : '') + (h.new_value - h.old_value).toFixed(4) }}
          </td>
        </tr>
      </tbody>
    </table>
    <p
      v-else
      class="mt-3 sk-body"
    >
      기록된 MDC 변경이 없습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { MdcHistoryEntry } from '~/composables/useTttmApi'

const props = defineProps<{ history: MdcHistoryEntry[] }>()
const sorted = computed(() => [...props.history].sort((a, b) => b.date.localeCompare(a.date)))
</script>
